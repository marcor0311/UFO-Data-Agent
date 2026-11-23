// Executes the shipped classic worker and its RPC handlers in Node, without a browser or GPU.
const {Worker} = require('node:worker_threads');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const sdkContext = {console, Blob, URL, performance, AbortController, TextEncoder, TextDecoder,
  setTimeout, clearTimeout, location:{origin:'null'}, navigator:{hardwareConcurrency:4,userAgent:'SDK-component-audit'}};
sdkContext.window=sdkContext; sdkContext.self=sdkContext;
vm.createContext(sdkContext);
vm.runInContext(fs.readFileSync(path.join(__dirname,'assets/vendor/maplibre-gl-5.24.0.js'),'utf8'),sdkContext);
const lib=sdkContext.maplibregl;
assert.equal(lib.getVersion(),'5.24.0');
const workerBlob=require('node:buffer').resolveObjectURL(lib.getWorkerUrl());
assert(workerBlob, 'The standalone SDK did not create its own worker bundle.');
const bootstrap = `
const {parentPort, MessageChannel, workerData} = require('node:worker_threads');
const fs = require('node:fs'), vm = require('node:vm');
const {ImageData} = require('/Users/marcorodriguez/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas');
class WorkerGlobalScope {}
const self = new WorkerGlobalScope(), subscriptions = new Map();
self.addEventListener = (type, fn) => { if (type === 'message') { const handler = data => fn({data}); subscriptions.set(fn, handler); parentPort.on('message', handler); } };
self.removeEventListener = (type, fn) => { const handler = subscriptions.get(fn); if (handler) parentPort.off('message', handler); };
self.postMessage = (data, options) => parentPort.postMessage(data, options?.transfer || []);
const location = {origin:'null', href:'file:///worker-audit.html'};
self.location = location;
const context = {self, WorkerGlobalScope, location, MessageChannel, ImageData, console,
  setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask, performance,
  fetch, AbortController, Blob, URL, TextDecoder, TextEncoder};
vm.runInNewContext(workerData.source, context, {filename:'maplibre-5.24.0-native-worker.js'});
if (!self.worker?.actor) throw Error('The MapLibre worker did not initialize.');
parentPort.postMessage({auditReady:true, handlers:Object.keys(self.worker.actor.messageHandlers)});
`;
(async () => {
  const worker = new Worker(bootstrap, {eval:true, workerData:{source:await workerBlob.text()}});
  const messages = [];
  let timer;
  try {
    const ready = await new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(Error('Worker RPC timed out.')), 5000);
      worker.on('error', reject);
      worker.on('message', message => {
        messages.push(message);
        if (message.auditReady) {
          assert(message.handlers.includes('LDT'));
          assert(message.handlers.includes('LT'));
          worker.postMessage({id:'audit-referrer', type:'SR', origin:'null',
            sourceMapId:'audit', data:'file:///worker-audit.html'});
        } else if (message.id === 'audit-referrer') {
          assert.equal(message.type, '<response>');
          assert.equal(message.error, null);
          worker.postMessage({id:'audit-remove', type:'RM', origin:'null', sourceMapId:'audit'});
        } else if (message.id === 'audit-remove') {
          assert.equal(message.type, '<response>');
          assert.equal(message.error, null);
          resolve(true);
        }
      });
    });
    const result = {maplibreVersion:lib.getVersion(),nativeStandaloneWorker:true,classicWorkerInitialized:ready, rpcResponses:2,
      handlerCount:messages[0].handlers.length,
      scope:'Classic worker execution and real MapLibre RPC in Node. Does not prove browser loading, tiles or GPU.'};
    fs.writeFileSync(path.join(__dirname, 'verificacion-experiencia/worker.json'), JSON.stringify(result,null,2)+'\n');
    console.log('Worker clásico inicia y responde al protocolo MapLibre; sin navegador/GPU.');
  } finally { clearTimeout(timer); await worker.terminate(); }
})().catch(error => { console.error(error); process.exitCode=1; });
