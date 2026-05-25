const https = require('https');
const url = 'https://cdn.jsdelivr.net/npm/marked/lib/marked.umd.js';
https.get(url, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
        const wrapper = data.toString();
        const marked = {};
        // 标准的 UMD wrapper: (function(root, factory) { ... })(this, function(exports) { ... });
        // marked 库会挂到 exports 上
        const exports = {};
        // 模拟 browser 环境
        const window = {};
        (new Function('exports', 'module', 'window', wrapper))(exports, { exports: exports }, window);
        
        // exports 就是 marked
        const m = exports;
        
        console.log('=== Common API check ===');
        console.log('typeof m.parse:', typeof m.parse);
        console.log('typeof m.Renderer:', typeof m.Renderer);
        console.log('typeof m.setOptions:', typeof m.setOptions);
        console.log('Has parseSync:', typeof m.parseSync);
        console.log('m.parse === m:', m.parse === m);
        
        // 测试1: 基本解析
        const testText = '好的！以下是会员信息\n\n| 字段 | 内容 |\n|------|------|\n| **姓名** | **鼠小弟** |\n\n描述。';
        const result = m.parse(testText);
        console.log('\n=== Test 1: basic ===');
        console.log('Type:', typeof result);
        console.log('String:', typeof result === 'string');
        console.log('Has [object Object]:', result.indexOf('[object Object]') >= 0);
        console.log('Preview:', result.substring(0, 300));
        
        // 测试2: 自定义 Renderer + setOptions
        const renderer = new m.Renderer();
        renderer.code = function() {
            const arg = arguments[0];
            const text = typeof arg === 'object' ? arg.text : arg;
            const lang = typeof arg === 'object' ? arg.lang : arguments[1];
            const langLabel = lang ? lang.toUpperCase() : '';
            const code = String(text).replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return '<pre><code>'+code+'</code></pre>';
        };
        renderer.table = function() {
            const arg = arguments[0];
            const header = typeof arg === 'object' ? arg.header : arg;
            const body = typeof arg === 'object' ? arg.body : arguments[1];
            return '<table><thead>'+header+'</thead><tbody>'+body+'</tbody></table>';
        };
        m.setOptions({ renderer: renderer, breaks: true, gfm: true });
        
        const r2 = m.parse(testText);
        console.log('\n=== Test 2: custom renderer ===');
        console.log('Type:', typeof r2);
        console.log('String:', typeof r2 === 'string');
        console.log('Has [object Object]:', r2.indexOf('[object Object]') >= 0);
        console.log('Preview:', r2.substring(0, 300));
        
        // 测试3: async
        const r3 = m.parse(testText, { async: true });
        console.log('\n=== Test 3: async ===');
        console.log('Type:', typeof r3);
        console.log('Is Promise:', r3 && typeof r3.then === 'function');
        
        // 测试4: HTML 字符
        const r4 = m.parse('<test> & "hello"');
        console.log('\n=== Test 4: HTML ===');
        console.log('Type:', typeof r4);
        console.log('Result:', r4.substring(0, 100));
        
        // 测试5: 空的输入
        const r5 = m.parse('');
        console.log('\n=== Test 5: empty ===');
        console.log('Type:', typeof r5);
        
        console.log('\n=== ALL DONE ===');
    });
}).on('error', e => console.error('Error:', e.message));
