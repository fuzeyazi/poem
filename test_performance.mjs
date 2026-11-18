import http from 'http';
import querystring from 'querystring';

const BASE_URL = 'localhost';
const PORT = 8080;

let token = '';
const testUsername = 'perfuser' + Date.now();

function makeRequest(path, method = 'GET', headers = {}, body = null) {
    return new Promise((resolve) => {
        const options = {
            hostname: BASE_URL,
            port: PORT,
            path: path,
            method: method,
            headers: {
                'Content-Type': 'application/json',
                ...headers
            }
        };

        const start = Date.now();
        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => {
                data += chunk;
            });
            res.on('end', () => {
                const duration = Date.now() - start;
                resolve({
                    status: res.statusCode,
                    duration: duration,
                    data: data
                });
            });
        });

        req.on('error', (e) => {
            resolve({
                status: 0,
                duration: Date.now() - start,
                data: null,
                error: e.message
            });
        });

        if (body) {
            req.write(body);
        }
        req.end();
    });
}

async function runTests() {
    console.log('=== 性能测试开始 ===\n');

    console.log('1. 注册测试用户');
    let result = await makeRequest('/user/register', 'POST', {}, JSON.stringify({
        username: testUsername,
        password: '123456'
    }));
    console.log(`   状态码: ${result.status}, 耗时: ${result.duration}ms`);
    console.log(`   响应: ${result.data || '无'}\n`);

    console.log('2. 用户登录 (使用刚注册的用户)');
    result = await makeRequest('/user/login', 'POST', {}, JSON.stringify({
        username: testUsername,
        password: '123456'
    }));
    console.log(`   状态码: ${result.status}, 耗时: ${result.duration}ms`);
    console.log(`   响应: ${result.data ? result.data.substring(0, 500) : '无'}\n`);
    
    if (result.status === 200 && result.data) {
        try {
            const json = JSON.parse(result.data);
            console.log('JSON解析:', JSON.stringify(json));
            token = json.data?.token || '';
        } catch (e) {
            console.log('解析失败:', e.message);
        }
    }

    console.log(`最终Token: ${token ? '已获取 (' + token.substring(0, 30) + '...)' : '未获取'}\n`);

    const authHeaders = token ? { token: token } : {};

    console.log('3. 单接口性能测试');
    console.log('='.repeat(70));
    console.log(`| ${'接口名称'.padEnd(25)} | ${'状态码'.padEnd(8)} | ${'响应时间'.padEnd(12)} | ${'数据大小'.padEnd(12)} |`);
    console.log('='.repeat(70));

    const testCases = [
        { name: 'GetCount', path: '/user/poetry/GetCount', auth: false },
        { name: 'GetAllDynasty', path: '/user/poetry/GetAllDynasty', auth: true },
        { name: 'GetPoemDateRondom', path: '/user/poetry/GetPoemDateRondom', auth: true },
        { name: 'GetPoemPage(20)', path: '/user/poetry/GetPoemPage?pageNum=1&pageSize=20', auth: true },
        { name: 'GetContentById/1', path: '/user/poetry/GetContentById/1', auth: true },
        { name: 'GetDynastyandpoem', path: '/user/poetry/GetDynastyandpoem', auth: true },
        { name: 'GetAllPoemName', path: '/user/poetry/GetAllPoemName', auth: true },
        { name: 'GetTypeDotaVo', path: '/user/poetry/GetTypeDotaVo', auth: true },
    ];

    for (const tc of testCases) {
        const headers = tc.auth ? authHeaders : {};
        result = await makeRequest(tc.path, 'GET', headers);
        const dataSize = result.data ? result.data.length + 'B' : '-';
        console.log(`| ${tc.name.padEnd(25)} | ${result.status.toString().padEnd(8)} | ${result.duration + 'ms'.padEnd(12)} | ${dataSize.padEnd(12)} |`);
    }
    console.log('='.repeat(70) + '\n');

    console.log('4. 中文参数接口测试');
    console.log('='.repeat(70));
    const chineseCases = [
        { name: 'GetPoemBydynasty(唐)', path: '/user/poetry/GetPoemBydynasty?' + querystring.stringify({ dynasty: '唐代' }), auth: true },
        { name: 'GetPoemByWriter(李白)', path: '/user/poetry/GetPoemByWriter?' + querystring.stringify({ name: '李白' }), auth: true },
        { name: 'GetPoemByType(送别)', path: '/user/poetry/GetPoemByType?' + querystring.stringify({ Type: '送别' }), auth: true },
    ];

    for (const tc of chineseCases) {
        const headers = tc.auth ? authHeaders : {};
        result = await makeRequest(tc.path, 'GET', headers);
        const dataSize = result.data ? result.data.length + 'B' : '-';
        console.log(`| ${tc.name.padEnd(25)} | ${result.status.toString().padEnd(8)} | ${result.duration + 'ms'.padEnd(12)} | ${dataSize.padEnd(12)} |`);
    }
    console.log('='.repeat(70) + '\n');

    console.log('5. 并发请求测试 (10次)');
    console.log('='.repeat(70));
    const concurrentTests = [
        { name: 'GetPoemPage', path: '/user/poetry/GetPoemPage?pageNum=1&pageSize=20', auth: true },
        { name: 'GetPoemDateRondom', path: '/user/poetry/GetPoemDateRondom', auth: true },
        { name: 'GetAllDynasty', path: '/user/poetry/GetAllDynasty', auth: true },
        { name: 'GetCount', path: '/user/poetry/GetCount', auth: false },
    ];

    for (const tc of concurrentTests) {
        console.log(`\n测试: ${tc.name}`);
        const headers = tc.auth ? authHeaders : {};
        const promises = [];
        const start = Date.now();
        for (let i = 0; i < 10; i++) {
            promises.push(makeRequest(tc.path, 'GET', headers));
        }
        const results = await Promise.all(promises);
        const totalDuration = Date.now() - start;
        
        const times = results.map(r => r.duration);
        const avgTime = Math.round(times.reduce((a, b) => a + b, 0) / times.length);
        const minTime = Math.min(...times);
        const maxTime = Math.max(...times);
        const successCount = results.filter(r => r.status === 200).length;

        console.log(`   总耗时: ${totalDuration}ms, 平均: ${avgTime}ms, 最小: ${minTime}ms, 最大: ${maxTime}ms`);
        console.log(`   成功率: ${successCount}/10`);
    }

    console.log('\n6. 高并发压力测试 (50次)');
    console.log('='.repeat(70));
    const highConcurrenceTests = [
        { name: 'GetPoemPage', path: '/user/poetry/GetPoemPage?pageNum=1&pageSize=20', auth: true },
        { name: 'GetCount', path: '/user/poetry/GetCount', auth: false },
    ];

    for (const tc of highConcurrenceTests) {
        console.log(`\n测试: ${tc.name}`);
        const headers = tc.auth ? authHeaders : {};
        const promises = [];
        const start = Date.now();
        for (let i = 0; i < 50; i++) {
            promises.push(makeRequest(tc.path, 'GET', headers));
        }
        const results = await Promise.all(promises);
        const totalDuration = Date.now() - start;
        
        const times = results.map(r => r.duration);
        const avgTime = Math.round(times.reduce((a, b) => a + b, 0) / times.length);
        const minTime = Math.min(...times);
        const maxTime = Math.max(...times);
        const successCount = results.filter(r => r.status === 200).length;
        const rps = Math.round(50 / (totalDuration / 1000));

        console.log(`   总耗时: ${totalDuration}ms`);
        console.log(`   平均响应: ${avgTime}ms, 最小: ${minTime}ms, 最大: ${maxTime}ms`);
        console.log(`   成功率: ${successCount}/50`);
        console.log(`   请求速率: ${rps} req/s`);
    }

    console.log('\n7. 登录接口性能测试');
    console.log('='.repeat(70));
    const loginPromises = [];
    const loginStart = Date.now();
    for (let i = 0; i < 5; i++) {
        loginPromises.push(makeRequest('/user/login', 'POST', {}, JSON.stringify({
            username: testUsername,
            password: '123456'
        })));
    }
    const loginResults = await Promise.all(loginPromises);
    const loginTotalDuration = Date.now() - loginStart;
    const loginTimes = loginResults.map(r => r.duration);
    const loginAvg = Math.round(loginTimes.reduce((a, b) => a + b, 0) / loginTimes.length);
    const loginSuccess = loginResults.filter(r => r.status === 200).length;
    
    console.log(`   总耗时: ${loginTotalDuration}ms, 平均: ${loginAvg}ms`);
    console.log(`   成功率: ${loginSuccess}/5`);

    console.log('\n=== 性能测试完成 ===');
}

runTests().catch(console.error);
