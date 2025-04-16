package com.fuze.potryservice.Aspect;

import cn.hutool.core.date.DateUtil;
import com.fuze.entity.Log;
import com.fuze.potryservice.interceptor.JwtTokenUserInterceptor;
import com.fuze.potryservice.service.LogService;
import com.fuze.result.Result;
import com.fuze.utils.JwtUtil;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
@Component
@Aspect
public class LogAspect {
@Autowired
    private LogService logService;
    private static final Logger log = LoggerFactory.getLogger(LogAspect.class);
    @Around("@annotation(autoLog)")
    public Result doAround(ProceedingJoinPoint joinPoint, AutoLog autoLog)throws Throwable{
        //操作内容，在value已经标识好了
        String title = autoLog.value();
        //获取当前更改时间
        String time= DateUtil.now();
        Log log = new Log(title, time);
        logService.addLog(log.getTitle(),log.getTime());
        Result proceed = (Result) joinPoint.proceed();
        return proceed;
    }
}
