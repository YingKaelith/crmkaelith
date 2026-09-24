"""Entrypoint for a persistent web host. TLS must terminate at the host's proxy.
No database, admin password or access token is embedded in this source.
"""
import os
import uvicorn


def server_port() -> int:
    try:
        port = int(os.environ.get('PORT', '8000'))
    except ValueError as exc:
        raise ValueError('PORT precisa ser um número inteiro.') from exc
    if not 1 <= port <= 65535:
        raise ValueError('PORT precisa estar entre 1 e 65535.')
    return port


def main() -> None:
    uvicorn.run('server.app:create_app', factory=True, host='0.0.0.0',
                port=server_port(), workers=1, proxy_headers=False, access_log=False)


if __name__ == '__main__':
    main()
