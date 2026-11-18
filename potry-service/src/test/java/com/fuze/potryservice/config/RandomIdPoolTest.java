package com.fuze.potryservice.config;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * 验证随机 id 池契约:SRANDMEMBER 抽样、池空经 loader 装载后重抽、
 * loader 空库返回空、Redis 异常整体降级返回空列表(由调用方回退 ORDER BY RAND())。
 */
@ExtendWith(MockitoExtension.class)
class RandomIdPoolTest {

    private static final String KEY = RandomIdPool.POTRY_POOL;

    @Mock
    private StringRedisTemplate stringRedisTemplate;
    @Mock
    private SetOperations<String, String> setOps;
    @InjectMocks
    private RandomIdPool randomIdPool;

    @BeforeEach
    void setUp() {
        lenient().when(stringRedisTemplate.opsForSet()).thenReturn(setOps);
    }

    @Test
    @DisplayName("池命中:直接解析为 Integer 列表,不回源")
    void poolHit() {
        when(setOps.randomMembers(eq(KEY), anyLong())).thenReturn(List.of("3", "7"));

        List<Integer> result = randomIdPool.randomIds(KEY, 2, () -> {
            fail("池命中时不应触发 loader");
            return List.of();
        });

        assertEquals(List.of(3, 7), result);
        verify(setOps, never()).add(anyString(), any(String[].class));
    }

    @Test
    @DisplayName("池空:loader 装载→add+1h 过期→重抽")
    void poolEmpty_loadsThenRedraws() {
        when(setOps.randomMembers(eq(KEY), anyLong()))
                .thenReturn(List.of())          // 首抽:池空
                .thenReturn(List.of("2"));      // 装载后重抽
        Supplier<List<Integer>> loader = () -> List.of(1, 2, 3);

        List<Integer> result = randomIdPool.randomIds(KEY, 1, loader);

        assertEquals(List.of(2), result);
        verify(setOps).add(eq(KEY), any(String[].class));
        verify(stringRedisTemplate).expire(eq(KEY), eq(1L), eq(TimeUnit.HOURS));
    }

    @Test
    @DisplayName("loader 空库:返回空列表,不写池")
    void loaderEmpty_returnsEmpty() {
        when(setOps.randomMembers(eq(KEY), anyLong())).thenReturn(List.of());

        List<Integer> result = randomIdPool.randomIds(KEY, 5, List::of);

        assertTrue(result.isEmpty());
        verify(setOps, never()).add(anyString(), any(String[].class));
        verify(stringRedisTemplate, never()).expire(anyString(), anyLong(), any(TimeUnit.class));
    }

    @Test
    @DisplayName("Redis 异常:整体降级返回空列表,loader 不触发(交给调用方回退 ORDER BY RAND())")
    void redisDown_degradesToEmpty() {
        when(setOps.randomMembers(eq(KEY), anyLong())).thenThrow(new RuntimeException("redis down"));

        List<Integer> result = randomIdPool.randomIds(KEY, 5, () -> {
            fail("Redis 异常路径不应触发 loader");
            return List.of();
        });

        assertTrue(result.isEmpty());
    }
}
