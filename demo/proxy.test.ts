import { createServer, request, type Server } from 'node:http';
import { afterEach, expect, it } from 'vitest';
import { localProxy } from './proxy';

const servers: Server[] = [];
async function listen(server: Server) {
    servers.push(server);
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('No port');
    return `http://127.0.0.1:${address.port}`;
}
afterEach(async () => {
    await Promise.all(
        servers.splice(0).map(
            (server) =>
                new Promise<void>((resolve) => {
                    server.closeAllConnections();
                    server.close(() => resolve());
                }),
        ),
    );
});

it('allows only local same-origin JSON requests to the fixed endpoint set', async () => {
    let forwarded = 0;
    const upstream = await listen(
        createServer((req, res) => {
            forwarded++;
            if (req.url === '/scale') {
                res.writeHead(302, { Location: 'http://example.com' });
                res.end();
            } else {
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end('{"data":[]}');
            }
        }),
    );
    const middleware = localProxy(upstream);
    const target = await listen(
        createServer((req, res) => {
            void middleware(req, res, () => {
                res.writeHead(404);
                res.end();
            });
        }),
    );
    expect((await fetch(target + '/api/config').then((r) => r.json())).target).toBe(upstream);
    expect((await fetch(target + '/api/v1/models')).status).toBe(200);
    expect(
        (await fetch(target + '/api/v1/models', { headers: { Origin: 'https://evil.example' } })).status,
    ).toBe(403);
    const badHostStatus = await new Promise<number | undefined>((resolve, reject) => {
        const req = request(target + '/api/v1/models', { headers: { Host: 'evil.example' } }, (res) => {
            res.resume();
            resolve(res.statusCode);
        });
        req.on('error', reject);
        req.end();
    });
    expect(badHostStatus).toBe(403);
    expect((await fetch(target + '/api/props')).status).toBe(404);
    expect((await fetch(target + '/api/decision?url=http://example.com', { method: 'POST' })).status).toBe(
        404,
    );
    expect((await fetch(target + '/api/decision', { method: 'POST', body: '{}' })).status).toBe(415);
    expect(
        (
            await fetch(target + '/api/decision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: ' '.repeat(2 * 1024 * 1024 + 1),
            })
        ).status,
    ).toBe(413);
    expect(forwarded).toBe(1);
    expect(
        (
            await fetch(target + '/api/scale', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: '{}',
            })
        ).status,
    ).toBe(502);
    expect(forwarded).toBe(2);
});
