//package com.fuze.potryservice.config;
//
//import com.fuze.potryservice.interceptor.JwtTokenUserInterceptor;
//import jakarta.annotation.Resource;
//import org.springframework.context.annotation.Configuration;
//import org.springframework.web.servlet.config.annotation.CorsRegistry;
//import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
//import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
//@Configuration
//public class ww implements WebMvcConfigurer {
//    @Resource
//    private JwtTokenUserInterceptor jwtTokenUserInterceptor;
//    @Resource
//    private ssss sss;
//    @Override
//    public void addInterceptors(InterceptorRegistry registry) {
//        // 跨域拦截器需放在最上面
//        registry.addInterceptor(sss).addPathPatterns("/**");
//        // 校验token的拦截器
//        registry.addInterceptor(jwtTokenUserInterceptor).addPathPatterns("/admin/**");
//    }
//}
