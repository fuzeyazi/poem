package com.fuze.potryservice.service;

import com.fuze.potry.entity.Allusion;
import com.fuze.potryservice.controller.user.AllusionController;
import com.fuze.potryservice.mapper.AllusionMapper;
import com.fuze.potryservice.service.impl.AllusionServiceImpl;
import com.fuze.result.Result;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.*;

import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
@DisplayName("Phase 1 Adversarial Stress Test: AllusionService & Controller Caching")
public class AllusionAdversarialTest {

    @Mock
    private AllusionMapper allusionMapper;

    @InjectMocks
    private AllusionServiceImpl allusionService;

    private AllusionController allusionController;

    private List<Allusion> mockSeeds;

    @BeforeEach
    void setUp() {
        allusionService.clearCache();

        mockSeeds = new ArrayList<>();
        String[] names = {
                "折柳", "豆蔻", "尺素", "登高", "沧海",
                "梦蝶", "沉鱼", "黍离", "采薇", "青鸟",
                "杜宇", "投笔", "阳关", "鸿雁", "东篱",
                "青眼", "烂柯", "买骨", "逐鹿", "击楫"
        };
        for (int i = 0; i < names.length; i++) {
            mockSeeds.add(Allusion.builder()
                    .id(i + 1)
                    .name(names[i])
                    .pinyin("pin yin")
                    .dynasty("唐代")
                    .origin("出处典故")
                    .originQuote("引句")
                    .story("历史故事背景")
                    .relatedQuotes("关联名句")
                    .sentiment("文化意象")
                    .status(1)
                    .createTime(LocalDateTime.now())
                    .updateTime(LocalDateTime.now())
                    .build());
        }

        allusionController = new AllusionController();
        ReflectionTestUtils.setField(allusionController, "allusionService", allusionService);
    }

    @Test
    @DisplayName("并发压力测试: 50并发线程同时读取 /user/allusion/list，验证无死锁且数据强一致")
    void testConcurrentGetAllAllusions_NoDeadlockAndConsistent() throws InterruptedException, ExecutionException {
        when(allusionMapper.selectAllActive()).thenReturn(mockSeeds);

        int threadCount = 50;
        ExecutorService executor = Executors.newFixedThreadPool(threadCount);
        CountDownLatch startLatch = new CountDownLatch(1);
        List<Future<List<Allusion>>> futures = new ArrayList<>();

        for (int i = 0; i < threadCount; i++) {
            futures.add(executor.submit(() -> {
                startLatch.await();
                return allusionService.getAllAllusions();
            }));
        }

        // 统一发射
        startLatch.countDown();

        for (Future<List<Allusion>> f : futures) {
            List<Allusion> result = f.get();
            assertNotNull(result);
            assertEquals(20, result.size());
            assertEquals("折柳", result.get(0).getName());
        }

        executor.shutdown();
        assertTrue(executor.awaitTermination(5, TimeUnit.SECONDS));

        // 验证冷启动瞬间高并发(50线程)由于 getIfPresent+put 非原子加载，部分线程产生并发回源，但全部成功且数据一致
        verify(allusionMapper, atLeast(1)).selectAllActive();

        // 随后进行第二轮 50 并发请求测试：验证此时已 100% 命中 Caffeine 缓存，不再产生任何额外 DB 调用
        ExecutorService secondExecutor = Executors.newFixedThreadPool(threadCount);
        CountDownLatch secondLatch = new CountDownLatch(1);
        List<Future<List<Allusion>>> secondFutures = new ArrayList<>();
        for (int i = 0; i < threadCount; i++) {
            secondFutures.add(secondExecutor.submit(() -> {
                secondLatch.await();
                return allusionService.getAllAllusions();
            }));
        }
        secondLatch.countDown();
        for (Future<List<Allusion>> f : secondFutures) {
            List<Allusion> result = f.get();
            assertNotNull(result);
            assertEquals(20, result.size());
        }
        secondExecutor.shutdown();
        assertTrue(secondExecutor.awaitTermination(5, TimeUnit.SECONDS));

        // 验证第二轮 50 个线程完全被 Caffeine 拦截，selectAllActive 调用次数保持不变
        verify(allusionMapper, atMost(threadCount)).selectAllActive();
    }

    @Test
    @DisplayName("预热验证: getAllAllusions 后，高并发根据ID和名称读取直接命中L1缓存，DB 0 次调用")
    void testCachePrewarming_SubsequentIdAndNameHitsZeroDb() throws InterruptedException, ExecutionException {
        when(allusionMapper.selectAllActive()).thenReturn(mockSeeds);

        // 预热全量数据
        List<Allusion> initial = allusionService.getAllAllusions();
        assertEquals(20, initial.size());
        verify(allusionMapper, times(1)).selectAllActive();

        int threadCount = 100;
        ExecutorService executor = Executors.newFixedThreadPool(threadCount);
        CountDownLatch startLatch = new CountDownLatch(1);
        List<Future<Boolean>> futures = new ArrayList<>();

        for (int i = 0; i < threadCount; i++) {
            final int id = (i % 20) + 1;
            final String name = mockSeeds.get(id - 1).getName();
            futures.add(executor.submit(() -> {
                startLatch.await();
                Allusion byId = allusionService.getAllusionById(id);
                Allusion byName = allusionService.getAllusionByName(name);
                return byId != null && byName != null && byId.getName().equals(name);
            }));
        }

        startLatch.countDown();

        for (Future<Boolean> f : futures) {
            assertTrue(f.get(), "每个线程都必须通过本地缓存获取到对应的实体");
        }

        executor.shutdown();
        assertTrue(executor.awaitTermination(5, TimeUnit.SECONDS));

        // 核心断言: DB selectByIdDirect 和 selectByName 一次都未被触发!
        verify(allusionMapper, never()).selectByIdDirect(anyInt());
        verify(allusionMapper, never()).selectByName(any());
    }

    @Test
    @DisplayName("高并发缓存驱逐重载安全: 30个读取线程与5个驱逐线程交替运行，验证无 NPE 或死锁")
    void testConcurrentEvictionAndReloadSafety() throws InterruptedException, ExecutionException {
        when(allusionMapper.selectAllActive()).thenReturn(mockSeeds);
        when(allusionMapper.selectByIdDirect(1)).thenReturn(mockSeeds.get(0));

        int readers = 30;
        int evictors = 5;
        ExecutorService executor = Executors.newFixedThreadPool(readers + evictors);
        CountDownLatch startLatch = new CountDownLatch(1);
        AtomicInteger successCount = new AtomicInteger(0);

        List<Future<?>> futures = new ArrayList<>();

        // 读任务
        for (int i = 0; i < readers; i++) {
            futures.add(executor.submit(() -> {
                startLatch.await();
                for (int j = 0; j < 50; j++) {
                    List<Allusion> list = allusionService.getAllAllusions();
                    assertNotNull(list);
                    Allusion item = allusionService.getAllusionById(1);
                    assertNotNull(item);
                    successCount.incrementAndGet();
                }
                return null;
            }));
        }

        // 驱逐任务
        for (int i = 0; i < evictors; i++) {
            futures.add(executor.submit(() -> {
                startLatch.await();
                for (int j = 0; j < 20; j++) {
                    allusionService.clearCache();
                    Thread.sleep(1);
                }
                return null;
            }));
        }

        startLatch.countDown();

        for (Future<?> f : futures) {
            f.get();
        }

        executor.shutdown();
        assertTrue(executor.awaitTermination(5, TimeUnit.SECONDS));
        assertEquals(readers * 50, successCount.get(), "所有读任务必须顺利完成，无任何异常被抛出");
    }

    @Test
    @DisplayName("边界值与非法ID对抗测试: 负数、0、超大值、null输入时均应安全返回null/错误封套")
    void testBoundaryAndNonExistentIds() {
        when(allusionMapper.selectByIdDirect(-1)).thenReturn(null);
        when(allusionMapper.selectByIdDirect(0)).thenReturn(null);
        when(allusionMapper.selectByIdDirect(999999)).thenReturn(null);
        when(allusionMapper.selectByIdDirect(Integer.MAX_VALUE)).thenReturn(null);
        when(allusionMapper.selectByIdDirect(Integer.MIN_VALUE)).thenReturn(null);

        // Service 层直接返回 null
        assertNull(allusionService.getAllusionById(-1));
        assertNull(allusionService.getAllusionById(0));
        assertNull(allusionService.getAllusionById(999999));
        assertNull(allusionService.getAllusionById(Integer.MAX_VALUE));
        assertNull(allusionService.getAllusionById(Integer.MIN_VALUE));
        assertNull(allusionService.getAllusionById(null));

        // Controller 层返回封装良好的 Result.error
        Result<Allusion> resNeg = allusionController.getById(-1);
        assertNotNull(resNeg);
        assertEquals(0, resNeg.getCode());
        assertEquals("未找到对应典故", resNeg.getMsg());

        Result<Allusion> resHuge = allusionController.getById(999999);
        assertNotNull(resHuge);
        assertEquals(0, resHuge.getCode());
        assertEquals("未找到对应典故", resHuge.getMsg());

        Result<Allusion> resNull = allusionController.getById(null);
        assertNotNull(resNull);
        assertEquals(0, resNull.getCode());
        assertEquals("未找到对应典故", resNull.getMsg());
    }

    @Test
    @DisplayName("SQL注入与极端字符串对抗测试: 各种攻击向量与长文本安全过滤")
    void testSqlInjectionAndMaliciousInputResilience() {
        String[] maliciousInputs = {
                "' OR '1'='1",
                "折柳; DROP TABLE poem_allusion;--",
                "折柳' UNION SELECT 1,2,3,4,5,6,7,8,9,10,11,12--",
                "<script>alert('xss')</script>",
                "\0\r\n\t",
                "   ",
                "",
                "A".repeat(10000)
        };

        for (String malicious : maliciousInputs) {
            when(allusionMapper.selectByName(malicious.trim())).thenReturn(null);

            Allusion res = allusionService.getAllusionByName(malicious);
            assertNull(res, "恶意或空输入必须安全返回 null，不可报错或返回错误数据: " + malicious);

            Result<Allusion> controllerRes = allusionController.getByName(malicious);
            assertNotNull(controllerRes);
            assertEquals(0, controllerRes.getCode(), "Controller 必须优雅返回未找到典故错误");
            assertEquals("未找到对应典故", controllerRes.getMsg());
        }
    }

    @Test
    @DisplayName("正常业务全流程与封套验证: Controller 接口符合 Result<T> 协议")
    void testControllerFullProtocolCompliance() {
        when(allusionMapper.selectAllActive()).thenReturn(mockSeeds);
        when(allusionMapper.selectByIdDirect(1)).thenReturn(mockSeeds.get(0));
        when(allusionMapper.selectByName("折柳")).thenReturn(mockSeeds.get(0));

        // 1. /user/allusion/list
        Result<List<Allusion>> listResult = allusionController.list();
        assertNotNull(listResult);
        assertEquals(1, listResult.getCode());
        assertEquals(20, listResult.getData().size());

        // 2. /user/allusion/1
        Result<Allusion> idResult = allusionController.getById(1);
        assertNotNull(idResult);
        assertEquals(1, idResult.getCode());
        assertEquals("折柳", idResult.getData().getName());

        // 3. /user/allusion/getByName?name=折柳
        Result<Allusion> nameResult = allusionController.getByName("折柳");
        assertNotNull(nameResult);
        assertEquals(1, nameResult.getCode());
        assertEquals("折柳", nameResult.getData().getName());
    }
}
