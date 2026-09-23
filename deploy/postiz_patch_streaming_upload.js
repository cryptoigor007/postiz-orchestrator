// Патч Postiz: потоковая загрузка файлов на диск (без буфера в памяти) + лимит 20 ГБ.
// Применяется в Dockerfile-слое поверх postiz-fixed:v1.47.1 (см. docs/SESSION_LOG.md).
const fs = require('fs');

const B = '/app/apps/backend/dist';
const files = {
  ctrl: B + '/apps/backend/src/public-api/routes/v1/public.integrations.controller.js',
  pipe: B + '/libraries/nestjs-libraries/src/upload/custom.upload.validation.js',
  stor: B + '/libraries/nestjs-libraries/src/upload/local.storage.js',
};

function patch(file, pairs) {
  let s = fs.readFileSync(file, 'utf8');
  let changed = false;
  for (const [from, to] of pairs) {
    if (s.includes(from)) {
      s = s.split(from).join(to);
      changed = true;
    }
  }
  if (changed) {
    fs.writeFileSync(file, s);
    console.log('patched', file);
  } else {
    console.log('skip', file);
  }
}

const diskStorage =
  "(0, platform_express_1.FileInterceptor)('file', { storage: require('multer').diskStorage({ " +
  "destination: (req, file, cb) => { const d = '/tmp/postiz-uploads'; require('fs').mkdirSync(d, { recursive: true }); cb(null, d); }, " +
  "filename: (req, file, cb) => cb(null, Date.now() + '-' + Math.random().toString(16).slice(2) + '.bin') }) })";

patch(files.ctrl, [["(0, platform_express_1.FileInterceptor)('file')", diskStorage]]);

const pipeOld = `if (!value.buffer || !Buffer.isBuffer(value.buffer)) {
            throw new common_1.BadRequestException('Invalid file upload.');
        }
        const detected = await fromBuffer(value.buffer);`;
const pipeNew = `let _head = value.buffer;
        if ((!_head || !Buffer.isBuffer(_head)) && value.path) {
            const _fs = require('fs');
            const _fd = _fs.openSync(value.path, 'r');
            const _buf = Buffer.alloc(4100);
            const _n = _fs.readSync(_fd, _buf, 0, 4100, 0);
            _fs.closeSync(_fd);
            _head = _buf.subarray(0, _n);
        }
        if (!_head || !Buffer.isBuffer(_head)) {
            throw new common_1.BadRequestException('Invalid file upload.');
        }
        const detected = await fromBuffer(_head);`;

patch(files.pipe, [
  [pipeOld, pipeNew],
  ['3 * 1024 * 1024 * 1024', '20 * 1024 * 1024 * 1024'],
]);

const storOld = 'const detected = await fromBuffer(file.buffer);';
const storNew = `const _head = (() => { if (file.buffer && Buffer.isBuffer(file.buffer)) return file.buffer; if (file.path) { const _fs = require('fs'); const _fd = _fs.openSync(file.path, 'r'); const _b = Buffer.alloc(4100); const _n = _fs.readSync(_fd, _b, 0, 4100, 0); _fs.closeSync(_fd); return _b.subarray(0, _n); } return null; })();
            const detected = await fromBuffer(_head);`;
const writeOld = '(0, fs_1.writeFileSync)(filePath, file.buffer);';
const writeNew = `if (file.path && !file.buffer) { (0, fs_1.copyFileSync)(file.path, filePath); try { (0, fs_1.unlinkSync)(file.path); } catch (e) {} } else { (0, fs_1.writeFileSync)(filePath, file.buffer); }`;

patch(files.stor, [
  [storOld, storNew],
  [writeOld, writeNew],
]);
