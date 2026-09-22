import { secureMockApiPlugin } from '../../shared/secureMockApiPlugin.mjs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function computeDiff(initial, current, keyPath = '') {
  const diff = {};
  if (initial === current) return diff;
  const allKeys = new Set([
    ...Object.keys(initial || {}),
    ...Object.keys(current || {}),
  ]);
  for (const key of allKeys) {
    const fullPath = keyPath ? `${keyPath}.${key}` : key;
    const oldVal = initial ? initial[key] : undefined;
    const newVal = current ? current[key] : undefined;
    if (oldVal === newVal) continue;
    if (
      oldVal !== null && newVal !== null &&
      typeof oldVal === 'object' && typeof newVal === 'object' &&
      !Array.isArray(oldVal) && !Array.isArray(newVal)
    ) {
      const nested = computeDiff(oldVal, newVal, fullPath);
      Object.assign(diff, nested);
    } else if (JSON.stringify(oldVal) !== JSON.stringify(newVal)) {
      diff[fullPath] = { old: oldVal, new: newVal };
    }
  }
  return diff;
}

const STATE_DIR = path.resolve(__dirname, '.mock-states');

function sanitizeSid(raw) {
  return String(raw || '').replace(/[^a-zA-Z0-9_-]/g, '');
}

function stateFile(sid) {
  return path.join(STATE_DIR, `${sanitizeSid(sid) || 'default'}.json`);
}

function ensureStateDir() {
  if (!fs.existsSync(STATE_DIR)) fs.mkdirSync(STATE_DIR, { recursive: true });
}

function readStateDoc(sid) {
  const filePath = stateFile(sid);
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

// ---------- synthetic attachment generators ----------

function utf16beHex(str) {
  let hex = 'FEFF';
  for (let i = 0; i < str.length; i += 1) {
    hex += str.charCodeAt(i).toString(16).padStart(4, '0');
  }
  return hex.toUpperCase();
}

function pdfEscapeAscii(str) {
  return String(str).replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');
}

function buildPdf(titleLines) {
  const safeLines = titleLines.slice(0, 6);
  let content = '';
  let y = 780;
  safeLines.forEach((line, idx) => {
    const size = idx === 0 ? 16 : 12;
    content += `BT /F1 ${size} Tf 50 ${y} Td <${utf16beHex(line)}> Tj ET\n`;
    y -= idx === 0 ? 34 : 22;
  });
  content += `BT /F2 10 Tf 50 ${y - 10} Td (Beijing Jiaotong University - Synthetic Attachment) Tj ET\n`;
  content += `BT /F2 9 Tf 50 ${y - 26} Td (Generated locally by the bjtu_mock sandbox. Not an official document.) Tj ET\n`;

  const objects = [];
  objects.push('<< /Type /Catalog /Pages 2 0 R >>');
  objects.push('<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
  objects.push('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R /F2 7 0 R >> >> /Contents 4 0 R >>');
  objects.push(`<< /Length ${Buffer.byteLength(content, 'binary')} >>\nstream\n${content}endstream`);
  objects.push('<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /Identity-H /DescendantFonts [6 0 R] >>');
  objects.push('<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 >>');
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
  objects.push(`<< /Title <${utf16beHex(safeLines[0] || 'attachment')} /Producer (bjtu_mock) /CreationDate (D:20260921090000+08'00') >>`);

  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((body, i) => {
    offsets.push(Buffer.byteLength(pdf, 'binary'));
    pdf += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xrefStart = Buffer.byteLength(pdf, 'binary');
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (let i = 1; i <= objects.length; i += 1) {
    pdf += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R /Info 8 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`;
  return Buffer.from(pdf, 'binary');
}

function buildDoc(fileName, titleLines, paragraphs) {
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const body = (paragraphs && paragraphs.length ? paragraphs : titleLines.slice(1))
    .map((p) => `<p>${esc(p)}</p>`).join('\n');
  const html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="utf-8">
<title>${esc(fileName)}</title>
<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->
<style>
@page { size: A4; margin: 2.54cm; }
body { font-family: SimSun, "Songti SC", serif; font-size: 12pt; line-height: 1.8; }
h1 { font-size: 16pt; text-align: center; font-family: SimHei, "Heiti SC", sans-serif; }
.meta { text-align: center; color: #666; font-size: 10.5pt; }
</style>
</head>
<body>
<h1>${esc(titleLines[0] || fileName)}</h1>
<p class="meta">北京交通大学　合成附件　BJTU-MOCK-${Date.now().toString().slice(-6)}</p>
${body}
<p>北京交通大学（合成文档，仅用于沙箱训练环境）</p>
</body>
</html>`;
  return Buffer.from(html, 'utf8');
}

function findAttachment(sid, attId) {
  const candidates = [sid, 'default'];
  for (const candidate of candidates) {
    const doc = readStateDoc(candidate);
    const state = doc && doc.current_state;
    if (!state) continue;
    for (const listKey of ['notices', 'news']) {
      const list = state[listKey] || [];
      for (const item of list) {
        const att = (item.attachments || []).find((a) => a.id === attId);
        if (att) return { att, parent: item, listKey };
      }
    }
  }
  return null;
}

function setupMiddleware(server) {
  if (!fs.existsSync(STATE_DIR)) fs.mkdirSync(STATE_DIR, { recursive: true });

  server.middlewares.use((req, res, next) => {
    const url = new URL(req.url, 'http://localhost');

    // POST /post?sid=xxx  {action:'set'|'set_current'|'reset', state}
    if (req.method === 'POST' && url.pathname === '/post') {
      const sid = sanitizeSid(url.searchParams.get('sid') || 'default');
      const filePath = stateFile(sid);
      const chunks = [];
      req.on('data', (chunk) => { chunks.push(chunk); });
      req.on('end', () => {
        try {
          const payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          const { action, state } = payload;
          let stored = fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : {};
          if (action === 'set') {
            stored = { initial_state: state, current_state: state };
          } else if (action === 'set_current') {
            stored.current_state = state;
            if (!stored.initial_state) stored.initial_state = state;
          } else if (action === 'reset') {
            stored.current_state = stored.initial_state || {};
          } else {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Unknown action' }));
            return;
          }
          ensureStateDir();
          fs.writeFileSync(filePath, JSON.stringify(stored, null, 2));
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, sid }));
        } catch (e) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: e.message }));
        }
      });
      return;
    }

    // GET /state?sid=xxx → current_state object (or {})
    if (req.method === 'GET' && url.pathname === '/state') {
      const sid = sanitizeSid(url.searchParams.get('sid') || 'default');
      const doc = readStateDoc(sid);
      res.setHeader('Cache-Control', 'no-cache, no-store');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify((doc && doc.current_state) || {}));
      return;
    }

    // GET /go?sid=xxx → {initial_state, current_state, state_diff}
    // Browser navigation without ?sid= (Accept: text/html) falls through to the SPA /go page.
    if (req.method === 'GET' && url.pathname === '/go') {
      const hasSid = url.searchParams.has('sid');
      const wantsHtml = (req.headers.accept || '').includes('text/html');
      if (wantsHtml && !hasSid) return next();
      const sid = sanitizeSid(url.searchParams.get('sid') || 'default');
      const doc = readStateDoc(sid);
      const initial = doc ? doc.initial_state || null : null;
      const current = doc ? doc.current_state || null : null;
      const state_diff = initial && current ? computeDiff(initial, current) : {};
      res.setHeader('Cache-Control', 'no-cache, no-store');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ initial_state: initial, current_state: current, state_diff }));
      return;
    }

    // GET|HEAD /files/:attachmentId?sid=xxx → real generated bytes
    if ((req.method === 'GET' || req.method === 'HEAD') && url.pathname.startsWith('/files/')) {
      const attId = decodeURIComponent(url.pathname.slice('/files/'.length));
      const sid = sanitizeSid(url.searchParams.get('sid') || 'default');
      const found = findAttachment(sid, attId);
      if (!found) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: `attachment not found: ${attId}` }));
        return;
      }
      const { att, parent } = found;
      const titleLines = [parent.title || att.fileName, att.fileName];
      const isPdf = (att.fileType || 'pdf') === 'pdf';
      const buf = isPdf
        ? buildPdf(titleLines)
        : buildDoc(att.fileName, titleLines, parent.body);
      const encodedName = encodeURIComponent(att.fileName || 'attachment');
      res.writeHead(200, {
        'Content-Type': isPdf ? 'application/pdf' : 'application/msword',
        'Content-Disposition': `attachment; filename="${encodedName}"; filename*=UTF-8''${encodedName}`,
        'Content-Length': buf.length,
        'Cache-Control': 'no-cache',
      });
      res.end(req.method === 'HEAD' ? undefined : buf);
      return;
    }

    next();
  });
}

export default defineConfig({
  plugins: [
    secureMockApiPlugin(),
    react(),
    {
      name: 'mock-api',
      configureServer: setupMiddleware,
      configurePreviewServer: setupMiddleware,
    },
  ],
  server: {
    host: true,
    port: 5188,
  },
  preview: {
    host: true,
    port: 5188,
  },
});
