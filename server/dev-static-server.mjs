import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PORT = Number(process.env.PORT || getArg('--port') || getArg('-p') || 8766);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const MIME = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.js', 'application/javascript; charset=utf-8'],
  ['.mjs', 'application/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.jpg', 'image/jpeg'],
  ['.jpeg', 'image/jpeg'],
  ['.gif', 'image/gif'],
  ['.svg', 'image/svg+xml'],
  ['.ico', 'image/x-icon'],
  ['.webp', 'image/webp'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
]);

function getArg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : '';
}

function isBlockedPath(urlPath) {
  const normalized = urlPath.replace(/\\/g, '/');
  return /^\/(?:(?:doc|muban|server)(?:\/|$)|(?:.*\/)?README\.md$|\.(?:git|github|vscode|agents|codex)(?:\/|$))/i
    .test(normalized);
}

function send(res, status, body, type = 'text/plain; charset=utf-8') {
  res.writeHead(status, {
    'Content-Type': type,
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  res.end(body);
}

async function resolveFile(urlPath) {
  let cleanPath;
  try {
    cleanPath = decodeURIComponent(urlPath);
  } catch {
    return null;
  }

  if (cleanPath === '/') cleanPath = '/index.html';
  if (cleanPath === '/codevis/' || cleanPath === '/codevis') cleanPath = '/codevis/index.html';

  const target = path.resolve(ROOT, `.${cleanPath}`);
  if (!target.startsWith(ROOT + path.sep) && target !== ROOT) return null;

  try {
    const info = await stat(target);
    if (info.isDirectory()) {
      const indexFile = path.join(target, 'index.html');
      const indexInfo = await stat(indexFile);
      return indexInfo.isFile() ? indexFile : null;
    }
    return info.isFile() ? target : null;
  } catch {
    return null;
  }
}

const server = http.createServer(async (req, res) => {
  if (!req.url || req.method !== 'GET') {
    send(res, 405, 'Method Not Allowed');
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
  if (isBlockedPath(url.pathname)) {
    send(res, 404, 'Not Found');
    return;
  }

  const file = await resolveFile(url.pathname);
  if (!file) {
    send(res, 404, 'Not Found');
    return;
  }

  try {
    const body = await readFile(file);
    send(res, 200, body, MIME.get(path.extname(file).toLowerCase()) || 'application/octet-stream');
  } catch {
    send(res, 500, 'Internal Server Error');
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`EngLab preview: http://127.0.0.1:${PORT}/`);
});
