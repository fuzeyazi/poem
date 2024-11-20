package com.fuze.potryservice.interceptor;

import com.fuze.constant.JwtClaimsConstant;
import com.fuze.context.BaseContext;
import com.fuze.properties.JwtProperties;
import com.fuze.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jdk.jfr.ContentType;
import lombok.extern.slf4j.Slf4j;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;
@Component
@Slf4j
public class JwtTokenUserInterceptor implements HandlerInterceptor {
    @Autowired
    private JwtProperties jwtProperties;
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String contentType= "text/event-stream";
        System.out.println("进入拦截器");
        if (!(handler instanceof HandlerMethod)) {
            System.out.println("当前拦截到的不是动态方法，直接放行");
            //当前拦截到的不是动态方法，直接放行
            return true;
        }
        String method = request.getMethod();
        if ("OPTIONS".equals(method)) {
            return true;
        }
        //1、从请求头中获取令牌
        String token = request.getHeader(jwtProperties.getUserTokenName());
        //2、校验令牌
        try {
            Claims claims = JwtUtil.parseJWT(jwtProperties.getUserSecretKey(), token);
            System.out.println(claims);
//             Long dagree = Long.valueOf(claims.get(JwtClaimsConstant.Dagerr).toString());
            Long userid = Long.valueOf(claims.get(JwtClaimsConstant.USER_ID).toString());
            //ThreadLocal设置当前登录用户id
//          BaseContext.setDagree(dagree);
            BaseContext.setCurrentId(userid);
                System.out.println("登录成功");
            //3、通过，放行
            return true;
        } catch (Exception ex) {
            //4、不通过，响应401状态码
            response.getWriter().write("{\"status\":\"401\",\"message\":\"" + ex + "\"}");
            response.setStatus(401);
            return false;
        }
    }
}
