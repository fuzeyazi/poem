package com.fuze.potryservice.handler;

import com.fuze.exception.BaseException;
import com.fuze.result.Result;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.sql.SQLIntegrityConstraintViolationException;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 全局异常处理的响应契约:业务异常透传消息;SQL 唯一键冲突解析出重复值拼"已存在";
 * 其余 SQL 异常归为"未知错误"。code 约定:1 成功,0 失败。
 */
class GlobalExceptionHandlerTest {

    private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

    @Test
    @DisplayName("业务异常(BaseException):code=0,msg 透传异常消息")
    void baseException_passesMessage() {
        Result<?> r = handler.exceptionHandler(new BaseException("古诗已存在"));
        assertEquals(0, r.getCode());
        assertEquals("古诗已存在", r.getMsg());
    }

    @Test
    @DisplayName("SQL 唯一键冲突:提取重复值拼'已存在'(现状:带引号原样拼接,含引号是已知怪癖)")
    void duplicateEntry_extractsValue() {
        SQLIntegrityConstraintViolationException ex = new SQLIntegrityConstraintViolationException(
                "Duplicate entry 'zhangsan' for key 'employee.idx_username'");
        Result<?> r = handler.exceptionHandler(ex);
        assertEquals(0, r.getCode());
        // split(" ")[2] = "'zhangsan'"(引号是实现的一部分,此处固化现状,修复引号时同步改断言)
        assertEquals("'zhangsan'已存在", r.getMsg());
    }

    @Test
    @DisplayName("非冲突 SQL 异常:归为未知错误")
    void otherSqlError_unknownMessage() {
        SQLIntegrityConstraintViolationException ex = new SQLIntegrityConstraintViolationException(
                "Data too long for column 'content'");
        Result<?> r = handler.exceptionHandler(ex);
        assertEquals(0, r.getCode());
        assertEquals("未知错误", r.getMsg());
    }
}
