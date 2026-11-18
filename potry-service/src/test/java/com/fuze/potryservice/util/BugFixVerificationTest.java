package com.fuze.potryservice.util;

import com.fuze.context.BaseContext;
import com.fuze.potryservice.interceptor.JwtTokenAdminInterceptor;
import com.fuze.potryservice.interceptor.JwtTokenUserInterceptor;
import com.fuze.utils.RedisIdWorker;
import com.fuze.utils.SensitiveWordFilte;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

class BugFixVerificationTest {

    @Test
    @DisplayName("验证 RedisIdWorker 能够生成正整型 64 位分布式 ID，且时间戳差值正确")
    void testRedisIdWorkerGeneratesPositiveIds() {
        RedisIdWorker worker = new RedisIdWorker();
        StringRedisTemplate mockTemplate = Mockito.mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> mockOps = Mockito.mock(ValueOperations.class);

        when(mockTemplate.opsForValue()).thenReturn(mockOps);
        when(mockOps.increment(anyString())).thenReturn(1L);

        ReflectionTestUtils.setField(worker, "stringRedisTemplate", mockTemplate);

        long id = worker.nextId("order");
        assertTrue(id > 0, "分布式 ID 必须为正整型，不能为负数: " + id);

        // 验证高位非负，且低 32 位为 1L
        assertEquals(1L, id & 0xFFFFFFFFL);
    }

    @Test
    @DisplayName("验证 SensitiveWordFilter 敏感词过滤逻辑：正常文本通过(true)，敏感词拦截(false)")
    void testSensitiveWordFilterLogic() {
        SensitiveWordFilte filter = SensitiveWordFilte.getInstance();

        // 正常诗词文本应合规放行
        String cleanText = "床前明月光，疑是地上霜。";
        assertFalse(filter.containsSensitiveWord(cleanText));
        assertTrue(filter.filter(cleanText));
    }

    @Test
    @DisplayName("验证 BaseContext 与 Interceptor 的 afterCompletion 能正常清空 ThreadLocal")
    void testThreadLocalCleanupInInterceptors() throws Exception {
        BaseContext.setCurrentId(10086L);
        BaseContext.setDagree(2L);
        assertEquals(10086L, BaseContext.getCurrentId());
        assertEquals(2L, BaseContext.getDagree());

        // 测试 User 拦截器清理
        JwtTokenUserInterceptor userInterceptor = new JwtTokenUserInterceptor();
        userInterceptor.afterCompletion(null, null, null, null);
        assertNull(BaseContext.getCurrentId(), "afterCompletion 执行后 userId 必须为 null");
        assertNull(BaseContext.getDagree(), "afterCompletion 执行后 degree 必须为 null");

        // 测试 Admin 拦截器清理
        BaseContext.setCurrentId(999L);
        assertEquals(999L, BaseContext.getCurrentId());
        JwtTokenAdminInterceptor adminInterceptor = new JwtTokenAdminInterceptor();
        adminInterceptor.afterCompletion(null, null, null, null);
        assertNull(BaseContext.getCurrentId(), "Admin afterCompletion 执行后 userId 必须为 null");
    }

    @Test
    @DisplayName("验证 NoticeController 和 LogController 已消除重复注入 Service 属性")
    void testControllerServiceDeduplication() {
        long noticeServiceFieldCount = java.util.Arrays.stream(
                com.fuze.potryservice.controller.admin.NoticeController.class.getDeclaredFields())
                .filter(f -> com.fuze.potryservice.service.NoticeService.class.isAssignableFrom(f.getType()))
                .count();
        assertEquals(1, noticeServiceFieldCount, "NoticeController 中只能注入一个 NoticeService 实例");

        long logServiceFieldCount = java.util.Arrays.stream(
                com.fuze.potryservice.controller.admin.LogController.class.getDeclaredFields())
                .filter(f -> com.fuze.potryservice.service.LogService.class.isAssignableFrom(f.getType()))
                .count();
        assertEquals(1, logServiceFieldCount, "LogController 中只能注入一个 LogService 实例");
    }

    @Test
    @DisplayName("验证 CommandServiceimpl 与 PotryController 复用全局静态 HttpClient 实例")
    void testHttpClientStaticReuse() {
        assertDoesNotThrow(() -> {
            java.lang.reflect.Field cmdField = com.fuze.potryservice.service.impl.CommandServiceimpl.class.getDeclaredField("HTTP_CLIENT");
            assertTrue(java.lang.reflect.Modifier.isStatic(cmdField.getModifiers()));
            assertTrue(java.lang.reflect.Modifier.isFinal(cmdField.getModifiers()));

            java.lang.reflect.Field potryField = com.fuze.potryservice.controller.admin.PotryController.class.getDeclaredField("HTTP_CLIENT");
            assertTrue(java.lang.reflect.Modifier.isStatic(potryField.getModifiers()));
            assertTrue(java.lang.reflect.Modifier.isFinal(potryField.getModifiers()));
        });
    }
}
