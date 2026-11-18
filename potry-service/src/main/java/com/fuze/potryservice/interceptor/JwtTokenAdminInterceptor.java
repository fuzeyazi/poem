package com.fuze.potryservice.interceptor;

import com.fuze.constant.JwtClaimsConstant;
import com.fuze.context.BaseContext;
import com.fuze.properties.JwtProperties;
import com.fuze.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 管理端JWT拦截器:与管理端登录同密钥(adminSecretKey)验签,
 * 与用户端(userSecretKey)物理隔离——普通用户token在此必然验签失败,实现角色隔离
 */
@Component
@Slf4j
public class JwtTokenAdminInterceptor implements HandlerInterceptor {
    @Autowired
    private JwtProperties jwtProperties;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if (!(handler instanceof HandlerMethod)) {
            return true;
        }
        if ("OPTIONS".equals(request.getMethod())) {
            return true;
        }
        String token = request.getHeader(jwtProperties.getAdminTokenName());
        try {
            Claims claims = JwtUtil.parseJWTWithLegacy(jwtProperties.getAdminSecretKey(), jwtProperties.getAdminLegacySecretKeys(), token);
            Long adminId = Long.valueOf(claims.get(JwtClaimsConstant.USER_ID).toString());
            BaseContext.setCurrentId(adminId);
            log.info("管理员鉴权通过, adminId={}", adminId);
            return true;
        } catch (Exception ex) {
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"status\":401,\"message\":\"管理员未登录或凭证无效\"}");
            response.setStatus(401);
            return false;
        }
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) throws Exception {
        // 请求结束后清理 ThreadLocal，防止管理端身份在线程池复用时泄漏
        BaseContext.removeAll();
    }
}
