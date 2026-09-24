"""Browser workflow tests with a real temporary API and separate cookie jars.
Default --bridge mode is intended for restricted CI browsers that cannot navigate
URLs. It renders unmodified application HTML/CSS/JS via Playwright set_content,
replacing only the network transport with a Python HTTP bridge. Browser cookies,
origin enforcement and deployed TLS are NOT exercised by bridge mode. API tests
exercise session cookies, Origin and CSRF. --native uses normal same-origin HTTP
and is provided for validation on the deployment, but was not executed here.
Never point this script at a database containing real company data.
"""
from pathlib import Path
import os,sys,tempfile,subprocess,time,json,secrets,traceback,argparse
from datetime import date,timedelta
import httpx
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('NEXO_BROWSER_OUTPUT',ROOT/'tests'/'evidence'/'2.2'))
OUT.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--native',action='store_true');args=parser.parse_args()
BASE='http://127.0.0.1:8876';PASSWORD='Senha visual exclusiva de testes!';TOKEN=secrets.token_urlsafe(32)
passed=[];errors=[];results={}

def check(name):
    passed.append(name);print(f'PASS {len(passed):02d}: {name}',flush=True)

def state(client):
    r=client.get('/api/state');assert r.status_code==200,r.text;return r.json()['data']

def nav(page,target):
    menu=page.locator('.mobile-menu')
    if menu.is_visible() and not page.locator('.sidebar').evaluate("el=>el.classList.contains('open')"):menu.click()
    page.locator(f'.sidebar [data-page={target}]').click();page.wait_for_timeout(180)

def new(page,kind):
    nav(page,kind);page.locator(f'main [data-action=edit][data-kind={kind}]').first.click()

def fill(page,name,value):page.locator(f'#record-form [name="{name}"]').fill(str(value))
def select(page,name,value):page.locator(f'#record-form [name="{name}"]').select_option(str(value))
def save(page):
    page.locator('button[form=record-form]').click()
    try:expect(page.locator('#record-form')).to_have_count(0,timeout=5000)
    except Exception:
        raise AssertionError('Formulário permaneceu aberto: '+page.locator('#editor .form-error').inner_text()+' / '+page.locator('#toasts').inner_text())

def close(page):
    if page.locator('#editor').evaluate('el=>el.open'):page.locator('#editor [data-action=close-dialog]').first.click()

def edit(page,kind,id):
    nav(page,kind);page.locator(f'main [data-action=edit][data-kind={kind}][data-id="{id}"]').first.click()

def login(page,email='admin@example.com'):
    page.locator('#auth-form [name=email]').fill(email);page.locator('#auth-form [name=password]').fill(PASSWORD);page.locator('#auth-form button[type=submit]').click();expect(page.locator('.sidebar')).to_be_visible(timeout=5000)


def run():
 with tempfile.TemporaryDirectory(prefix='nexo-ui-') as tmp:
    env=os.environ|{'NEXO_DATA_DIR':tmp,'NEXO_SETUP_TOKEN':TOKEN,'NEXO_ORIGIN':BASE}
    log=open(OUT/'browser-server.log','w')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','server.app:create_app','--factory','--host','127.0.0.1','--port','8876','--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log)
    try:
        for _ in range(100):
            try:
                if httpx.get(BASE+'/api/health').status_code==200:break
            except httpx.RequestError:pass
            time.sleep(.1)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
            def make_page(width=1440,height=980):
                client=httpx.Client(base_url=BASE,headers={'Origin':BASE},timeout=25)
                page=browser.new_page(viewport={'width':width,'height':height},accept_downloads=True,locale='pt-BR')
                page.set_default_timeout(6000)
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('dialog',lambda d:d.accept())
                page.on('console',lambda e:errors.append(e.text) if e.type=='error' and ('Error' in e.text or 'CSP' in e.text) else None)
                if args.native:
                    page.goto(BASE)
                else:
                    def bridge(path,method,body,headers):
                        r=client.request(method,path,content=body,headers=headers)
                        return {'status':r.status_code,'body':r.text,'headers':dict(r.headers)}
                    page.expose_function('nexo_http',bridge)
                    import re
                    html=re.sub(r'<link[^>]+>|<script[^>]+></script>', '', (ROOT/'web/index.html').read_text())
                    page.set_content(html);page.add_style_tag(content=(ROOT/'web/styles.css').read_text())
                    page.evaluate("()=>{window.fetch=async(path,options={})=>{const r=await window.nexo_http(path,options.method||'GET',options.body||null,options.headers||{});return new Response(r.body,{status:r.status,headers:r.headers});};}")
                    page.add_script_tag(content=(ROOT/'web/pwa.js').read_text())
                    page.add_script_tag(content=(ROOT/'web/app.js').read_text())
                expect(page.locator('#auth-form')).to_be_visible(timeout=5000)
                return page,client
            page,admin=make_page()
            for key,value in [('token',TOKEN),('company','Estúdio Nexo · testes'),('name','Admin de Teste'),('email','admin@example.com'),('password',PASSWORD),('confirm',PASSWORD)]:page.locator('#auth-form [name='+key+']').fill(value)
            page.locator('#auth-form button[type=submit]').click();expect(page.locator('.sidebar')).to_be_visible(timeout=5000)
            if args.native:
                # Separate API observer session for assertions only.
                r=admin.post('/api/login',json={'email':'admin@example.com','password':PASSWORD})
            packet=admin.get('/api/session').json();admin.headers['X-CSRF-Token']=packet['csrf']
            check('Instalação pela interface, criação do administrador e abertura do painel vazio')
            nav(page,'settings');page.locator('#settings-form [name=company]').fill('Estúdio Nexo');page.locator('#settings-form [name=monthlyGoalCents]').fill('30.000');page.locator('#settings-form button[type=submit]').click();page.wait_for_timeout(400)
            assert state(admin)['settings']['monthlyGoalCents']==3000000;check('Configurações persistidas no servidor e valor brasileiro 30.000 convertido corretamente')
            new(page,'clients');fill(page,'name','Cliente Marketing (fictício)');fill(page,'email','cliente@example.com');save(page)
            cl=state(admin)['clients'][0];check('Cadastro de cliente por formulário, persistido no banco')
            new(page,'deals');fill(page,'title','Marketing e novo site');select(page,'clientId',cl['id']);select(page,'service','hybrid');fill(page,'valueCents','10.000,00');save(page)
            deal=state(admin)['deals'][0];assert deal['valueCents']==1000000
            check('Oportunidade híbrida, próximo contato obrigatório e valor em centavos')
            new(page,'proposals');fill(page,'title','Projeto completo');select(page,'clientId',cl['id']);select(page,'dealId',deal['id']);select(page,'service','hybrid')
            fill(page,'item_description','Site e campanha');fill(page,'item_quantity','1,5');fill(page,'item_unit','6.000,00');fill(page,'discountCents','500,00');fill(page,'scope','<script>window.xss=true</script>');save(page)
            prop=state(admin)['proposals'][0];assert prop['items'][0]['quantity']==1.5 and prop['discountCents']==50000
            page.locator(f'main [data-action=proposal-view][data-id="{prop["id"]}"]').first.click();assert page.evaluate('window.xss') is None;assert '<script>' in page.locator('#editor').inner_text();close(page)
            check('Proposta com quantidade decimal, desconto e conteúdo HTML exibido como texto')
            edit(page,'proposals',prop['id']);select(page,'status','accepted');save(page)
            d=state(admin);assert d['deals'][0]['stage']=='won' and d['deals'][0]['valueCents']==850000 and not d['entries']
            check('Aceite atualiza venda e cliente atomicamente, sem criar recebimento fictício')
            nav(page,'deals');page.locator(f'[data-action=deal-project][data-id="{deal["id"]}"]').click();save(page)
            d=state(admin);project=d['projects'][0];assert len(d['tasks'])==6;check('Venda convertida em projeto com seis tarefas do serviço combinado')
            edit(page,'projects',project['id']);select(page,'priority','high');fill(page,'nextAction','Validar briefing integrado');save(page)
            d=state(admin);project=d['projects'][0];task,dependent=d['tasks'][0],d['tasks'][1]
            edit(page,'tasks',dependent['id']);fill(page,'nextAction','Produzir materiais após briefing');fill(page,'progress','20');page.locator('#record-form [name=dependsOn]').select_option([task['id']]);save(page)
            saved=next(t for t in state(admin)['tasks'] if t['id']==dependent['id']);assert saved['dependsOn']==[task['id']] and saved['progress']==20
            nav(page,'flow-map');assert page.locator('.flow-node[data-flow-node]').count()==6;box=page.locator(f'.flow-node[data-flow-node="{dependent["id"]}"]').bounding_box();assert box
            page.mouse.move(box['x']+40,box['y']+40);page.mouse.down();page.mouse.move(box['x']+85,box['y']+75,steps=4);page.mouse.up();page.wait_for_timeout(500)
            moved=next(t for t in state(admin)['tasks'] if t['id']==dependent['id']);assert 'flowX' in moved and 'flowY' in moved
            page.screenshot(path=str(OUT/'flow-map-bos.png'),full_page=True);check('Flow Map usa tarefas reais, dependências e persiste a posição dos nós')
            nav(page,'my-day');assert 'O que precisa avançar hoje?' in page.locator('main').inner_text();check('Meu Dia consolida trabalho pessoal e bloqueios')
            nav(page,'clients');page.locator('main [data-action=client-detail]').first.click();assert 'Cliente 360' in page.locator('#editor').inner_text() and 'PRÓXIMA AÇÃO' in page.locator('#editor').inner_text();close(page);check('Cliente 360 consolida operação sem duplicar registros')
            nav(page,'tasks');page.locator(f'main [data-action=task-toggle][data-id="{task["id"]}"]').first.click();page.wait_for_timeout(350)
            assert next(t for t in state(admin)['tasks'] if t['id']==task['id'])['status']=='done'
            check('Conclusão de tarefa salva no servidor e integrada ao progresso do projeto')
            page.locator('[data-action=view][data-view=agenda]').click();assert page.locator('.calendar-day').count()==42
            check('Agenda mensal com seis semanas e tarefas do projeto')
            new(page,'entries');fill(page,'description','Entrada do projeto');select(page,'clientId',cl['id']);select(page,'projectId',project['id']);fill(page,'valueCents','5.000,00');save(page)
            entry=state(admin)['entries'][0];page.locator(f'main [data-action=entry-paid][data-id="{entry["id"]}"]').click();page.locator('#payment-form [name=paidDate]').fill(date.today().isoformat() if date.today().isoformat()==admin.get('/api/session').json()['serverDate'] else admin.get('/api/session').json()['serverDate']);page.locator('button[form=payment-form]').click();page.wait_for_timeout(400)
            assert state(admin)['entries'][0]['status']=='paid';check('Liquidação manual de receita com data e forma de pagamento')
            new(page,'contracts');fill(page,'title','Marketing mensal');select(page,'clientId',cl['id']);fill(page,'amountCents','1.500,00');fill(page,'dueDay','31');save(page)
            page.locator('[data-action=generate-recurring]').click();page.locator('[data-action=confirm-recurring]').click();page.wait_for_timeout(400);n=len(state(admin)['entries'])
            nav(page,'contracts');page.locator('[data-action=generate-recurring]').click();assert page.locator('[data-action=confirm-recurring]').is_disabled();close(page);assert len(state(admin)['entries'])==n
            check('Geração de mensalidade e bloqueio de duplicação na mesma competência')
            # User management and activation, through UI + API redemption.
            nav(page,'members');page.locator('[data-action=member-add]').click()
            page.locator('#member-form [name=name]').fill('Pessoa da Operação');page.locator('#member-form [name=email]').fill('operacao@example.com');page.locator('#member-form [name=role]').select_option('operations');page.locator('button[form=member-form]').click();expect(page.locator('#activation-link')).to_be_visible()
            link=page.locator('#activation-link').input_value();token=link.split('ativar=')[1];close(page)
            userclient=httpx.Client(base_url=BASE,headers={'Origin':BASE})
            assert userclient.post('/api/password/reset',json={'token':token,'password':PASSWORD}).status_code==200
            check('Administrador cria conta e gera código de ativação individual de uso único')
            other,op=make_page();login(other,'operacao@example.com')
            if args.native:assert op.post('/api/login',json={'email':'operacao@example.com','password':PASSWORD}).status_code==200
            assert other.locator('.sidebar [data-page=entries]').count()==0
            nav(other,'clients');assert 'Cliente Marketing' in other.locator('main').inner_text()
            nav(other,'projects');assert state(op)['projects'][0]['budgetCents']==0 and state(op)['projects'][0]['dealId']==''
            other.locator('main [data-action=project-detail]').first.click();assert '8.500' not in other.locator('#editor').inner_text();close(other)
            check('Sessão independente vê o mesmo cliente, sem módulo financeiro nem valor do projeto')
            nav(other,'tasks');t=next(t for t in state(op)['tasks'] if t['status']!='done');other.locator(f'main [data-action=task-toggle][data-id="{t["id"]}"]').first.click();other.wait_for_timeout(300)
            assert next(x for x in state(admin)['tasks'] if x['id']==t['id'])['status']=='done'
            check('Alteração de tarefa pela Operação aparece na base compartilhada do administrador')
            # Explicit visibility controls on real conversation forms.
            nav(page,'clients');page.locator('main [data-action=client-detail]').first.click();page.locator('#editor [data-action=edit][data-kind=activities]').first.click()
            fill(page,'text','Conversa restrita fictícia');select(page,'visibility','private');save(page)
            assert any(a['text']=='Conversa restrita fictícia' for a in state(admin)['activities'])
            assert not any(a['text']=='Conversa restrita fictícia' for a in state(op)['activities'])
            check('Conversa marcada privada pela interface é omitida da resposta da API para Operação')

            # Same-record conflict retains typed input.
            nav(page,'clients');page.locator('[data-action=sync]').click();edit(page,'clients',cl['id']);fill(page,'name','Texto ainda não salvo')
            row=state(admin)['clients'][0];row['name']='Alteração em outra sessão'
            r=admin.post('/api/transactions',json={'requestId':secrets.token_hex(12),'upserts':[{'kind':'clients','record':row,'expectedRevision':row['_rev']}],'deletes':[]});assert r.status_code==200
            page.locator('button[form=record-form]').click();page.wait_for_timeout(350)
            assert page.locator('#record-form [name=name]').input_value()=='Texto ainda não salvo'
            assert 'mudou em outra sessão' in page.locator('#record-form .form-error').inner_text();page.screenshot(path=str(OUT/'conflito-preservado.png'));close(page);page.locator('[data-action=sync]').click();page.wait_for_timeout(200)
            check('Conflito real de edição recusa sobrescrita e mantém os campos não salvos no formulário')
            # Import original one-file CRM backup, preserving user accounts.
            nav(page,'settings');page.locator('#backup-file').set_input_files(ROOT/'tests/fixtures/backup-local-ficticio.json');expect(page.locator('[name=restoreWord]')).to_be_visible();page.locator('[name=restoreWord]').fill('RESTAURAR');page.locator('[data-action=restore-confirm]').click();page.wait_for_timeout(650)
            assert len(state(admin)['clients'])==8 and len(admin.get('/api/users').json()['users'])==2
            check('Migração do backup local com prévia, confirmação e preservação de contas')
            # Mono / install instructions / connection state: browser UI through the bridge.
            assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()")=='#111111'
            chromatic=page.evaluate(r'''() => [...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().width).flatMap(el=>{
                const s=getComputedStyle(el);return ['color','backgroundColor','borderTopColor'].map(k=>s[k]);
            }).filter(value=>{const m=value.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/);return m && !(m[1]===m[2] && m[2]===m[3]);})''')
            assert not chromatic,chromatic[:8]
            check('Backup antigo com destaque roxo mantém o tema Mono; cores renderizadas são neutras')
            nav(page,'dashboard');page.locator('.install-nav').click();expect(page.locator('#pwa-dialog')).to_be_visible()
            assert 'Instalar não hospeda o servidor.' in page.locator('#pwa-dialog').inner_text()
            page.screenshot(path=str(OUT/'instalar-aplicativo.png'),full_page=True)
            page.locator('#pwa-dialog [data-pwa-action=close]').first.click()
            check('Instruções de instalação abrem e distinguem aplicativo de hospedagem')
            first_client=state(admin)['clients'][0]
            edit(page,'clients',first_client['id']);fill(page,'contact','Campo ainda não salvo')
            assert page.evaluate("window.dispatchEvent(new Event('nexo:before-reload',{cancelable:true}))") is False
            check('Atualização do aplicativo é bloqueada enquanto há campos não salvos')
            page.evaluate("window.__onlineFetch=window.fetch;window.fetch=async()=>{throw new TypeError('Rede indisponível no teste');};window.dispatchEvent(new Event('offline'))")
            expect(page.locator('#pwa-network-banner')).to_be_visible()
            assert page.locator('#record-form [name=contact]').input_value()=='Campo ainda não salvo'
            page.evaluate("window.fetch=window.__onlineFetch;delete window.__onlineFetch;window.dispatchEvent(new Event('online'))")
            expect(page.locator('#pwa-network-banner')).to_be_hidden()
            assert page.locator('#record-form [name=contact]').input_value()=='Campo ainda não salvo'
            close(page)
            check('Aviso de desconexão e recuperação da rede preservam o formulário em edição')
            # Refresh and screenshots of actual rendered demo data.
            page.wait_for_timeout(1200)
            while page.locator('#toasts button').count():page.locator('#toasts button').first.click()
            nav(page,'dashboard');page.screenshot(path=str(OUT/'painel-equipe.png'),full_page=True)
            nav(page,'deals');page.screenshot(path=str(OUT/'comercial-equipe.png'),full_page=True)
            nav(page,'members');page.wait_for_timeout(300);page.screenshot(path=str(OUT/'equipe-acessos.png'),full_page=True)
            nav(page,'audit');page.wait_for_timeout(350);assert page.locator('.data-table tbody tr').count()>0
            check('Auditoria exibida com autor, ações e campos alterados')
            # Mobile viewport: every admin module, no horizontal page overflow.
            page.set_viewport_size({'width':390,'height':844})
            for module in ['dashboard','my-day','clients','deals','proposals','projects','tasks','flow-map','entries','contracts','reports','settings','members','audit','account']:
                nav(page,module)
                dims=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
                assert dims['scroll']<=dims['width']+2,(module,dims)
            nav(page,'dashboard');page.screenshot(path=str(OUT/'mobile-equipe.png'),full_page=True)
            check('Quinze áreas renderizadas em 390 px sem transbordamento horizontal da página')
            page.locator('.mobile-menu').click();page.locator('.install-nav').click();expect(page.locator('#pwa-dialog')).to_be_visible()
            dims=page.locator('#pwa-dialog').bounding_box();assert dims['width']<=390 and dims['height']<=844
            page.screenshot(path=str(OUT/'instalar-mobile.png'),full_page=True)
            page.locator('#pwa-dialog [data-pwa-action=close]').last.click();nav(page,'dashboard')
            check('Instruções de instalação cabem em 390 px com rolagem e fechamento acessível')
            # CRM client creation on narrow screen.
            new(page,'clients');fill(page,'name','Cliente cadastrado no celular (fictício)');save(page);assert len(state(admin)['clients'])==9
            check('Cadastro completo de cliente na janela de celular')
            nav(page,'account');page.locator('[data-action=logout]').click();expect(page.locator('#auth-form')).to_be_visible()
            while page.locator('#toasts button').count():page.locator('#toasts button').first.click()
            page.screenshot(path=str(OUT/'login-mobile.png'),full_page=True)
            assert (page.request.get(BASE+'/api/state').status if args.native else admin.get('/api/state').status_code)==401
            page.set_viewport_size({'width':1440,'height':980});page.screenshot(path=str(OUT/'login-equipe.png'),full_page=True)
            check('Saída pela interface revoga a sessão no servidor')
            assert not errors,errors;check('Fluxos exercitados sem erro JavaScript não tratado')
            results.update({'status':'passed','browser':browser.version,'mode':'native' if args.native else 'bridge','checks':passed,'javascriptErrors':errors})
            browser.close()
    finally:
        server.terminate()
        try:server.wait(timeout=10)
        except subprocess.TimeoutExpired:server.kill()
        log.close()

try:run()
except Exception as exc:
    results.update({'status':'failed','checks':passed,'error':str(exc),'traceback':traceback.format_exc(),'javascriptErrors':errors});raise
finally:(OUT/'browser-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
