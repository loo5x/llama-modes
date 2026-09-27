import type { IncomingMessage, ServerResponse } from 'node:http';

export function localTarget(input: string): string {
    const url = new URL(input);
    if (
        url.protocol !== 'http:' ||
        !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) ||
        url.username ||
        url.password ||
        url.pathname !== '/' ||
        url.search ||
        url.hash
    ) {
        throw new Error('Use an HTTP loopback URL with a port, such as http://127.0.0.1:8080');
    }
    if (url.hostname === 'localhost') url.hostname = '127.0.0.1';
    return url.origin;
}

const endpoints = new Map([
    ['/v1/models', 'GET'],
    ['/decision', 'POST'],
    ['/scale', 'POST'],
    ['/v1/chat/completions', 'POST'],
]);

export function localProxy(target: string) {
    const upstream = localTarget(target);
    return async (req: IncomingMessage, res: ServerResponse, next: () => void) => {
        if (!req.url?.startsWith('/api/')) return next();
        const sendError = (status: number, message: string) => {
            res.writeHead(status, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: { message } }));
        };
        const allowedHosts = [
            `127.0.0.1:${req.socket.localPort}`,
            `localhost:${req.socket.localPort}`,
            `[::1]:${req.socket.localPort}`,
        ];
        if (!req.headers.host || !allowedHosts.includes(req.headers.host))
            return sendError(403, 'Local host required');
        const origin = req.headers.origin;
        if (origin && origin !== `http://${req.headers.host}`)
            return sendError(403, 'Same-origin requests only');
        if (req.headers['sec-fetch-site'] === 'cross-site')
            return sendError(403, 'Cross-site request rejected');
        if (req.url === '/api/config' && req.method === 'GET') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ target: upstream }));
            return;
        }
        const path = req.url.slice(4);
        if (endpoints.get(path) !== req.method) return sendError(404, 'Unsupported endpoint or method');
        if (req.method === 'POST' && req.headers['content-type']?.split(';')[0].trim() !== 'application/json')
            return sendError(415, 'JSON requests only');
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 120_000);
        res.on('close', () => controller.abort());
        try {
            const chunks: Buffer[] = [];
            let size = 0;
            for await (const chunk of req) {
                size += chunk.length;
                if (size > 2 * 1024 * 1024) return sendError(413, 'Request exceeds 2 MiB');
                chunks.push(Buffer.from(chunk));
            }
            const response = await fetch(upstream + path, {
                method: req.method,
                body: req.method === 'POST' ? Buffer.concat(chunks) : undefined,
                headers: { 'Content-Type': 'application/json' },
                redirect: 'error',
                signal: controller.signal,
            });
            const body = await response.text();
            res.writeHead(response.status, {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-store',
            });
            res.end(body);
        } catch (error) {
            if (!res.destroyed)
                sendError(
                    controller.signal.aborted ? 504 : 502,
                    controller.signal.aborted
                        ? 'llama-server request timed out'
                        : `Cannot reach llama-server at ${upstream}: ${error instanceof Error ? error.message : 'connection failed'}`,
                );
        } finally {
            clearTimeout(timer);
        }
    };
}
