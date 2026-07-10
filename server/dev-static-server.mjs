import http from 'node:http';
import { readFile, realpath, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PORT = Number(process.env.PORT || getArg('--port') || getArg('-p') || 8766);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ROOT_REAL = await realpath(ROOT);
const PUBLIC_DIRECTORIES = new Set(['pages', 'shared', 'UI', 'codevis']);
const PUBLIC_ROOT_FILES = new Set(['index.html', 'sw.js']);

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

function normalizedPublicPath(urlPath) {
  let normalized;
  try {
    normalized = decodeURIComponent(urlPath).replace(/\\/g, '/');
  } catch {
    return '';
  }
  if (normalized.includes('\0')) return '';
  if (normalized === '/') return '/index.html';
  if (normalized === '/codevis/' || normalized === '/codevis') return '/codevis/index.html';
  const segments = normalized.split('/').filter(Boolean);
  if (segments.some((segment) => segment === '.' || segment === '..')) return '';
  if (segments.length === 1 && PUBLIC_ROOT_FILES.has(segments[0])) return normalized;
  if (segments.length > 1 && PUBLIC_DIRECTORIES.has(segments[0])) return normalized;
  return '';
}

function isWithin(candidate, root) {
  const relative = path.relative(root, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
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
  const cleanPath = normalizedPublicPath(urlPath);
  if (!cleanPath) return null;

  const target = path.resolve(ROOT, `.${cleanPath}`);
  const firstSegment = cleanPath.split('/').filter(Boolean)[0];
  const publicRoot = PUBLIC_ROOT_FILES.has(firstSegment) ? ROOT : path.resolve(ROOT, firstSegment);
  if (!isWithin(target, publicRoot)) return null;

  try {
    const publicRootReal = await realpath(publicRoot);
    const info = await stat(target);
    if (info.isDirectory()) {
      const indexFile = path.join(target, 'index.html');
      const indexInfo = await stat(indexFile);
      if (!indexInfo.isFile()) return null;
      const realIndex = await realpath(indexFile);
      return isWithin(realIndex, publicRootReal) && isWithin(realIndex, ROOT_REAL) ? realIndex : null;
    }
    if (!info.isFile()) return null;
    const realTarget = await realpath(target);
    return isWithin(realTarget, publicRootReal) && isWithin(realTarget, ROOT_REAL) ? realTarget : null;
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
