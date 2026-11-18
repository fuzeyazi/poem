package com.fuze.potryservice.config;

import com.fuze.json.JacksonObjectMapper;
import com.fuze.potryservice.interceptor.JwtTokenAdminInterceptor;
import com.fuze.potryservice.interceptor.JwtTokenUserInterceptor;
import okhttp3.Response;
import org.aopalliance.intercept.Interceptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurationSupport;

import java.util.List;

@Configuration
public class WebMvcConfiguration extends WebMvcConfigurationSupport {
@Autowired
    private JwtTokenUserInterceptor jwtTokenUserInterceptor;
    @Autowired
    private JwtTokenAdminInterceptor jwtTokenAdminInterceptor;

    protected void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(jwtTokenUserInterceptor)
                .addPathPatterns("/user/**")
                .excludePathPatterns("/user/login")
                .excludePathPatterns("/user/register")
                .excludePathPatterns("/user/login/code")
                .excludePathPatterns("/user/login/email")
                .addPathPatterns("/ai/**")
                .excludePathPatterns("/user/forget");
        //管理端鉴权:登录/验证码/游客公告接口放行,其余/admin/**与/notice/**需管理端JWT(adminSecretKey验签,与用户端密钥隔离)
        registry.addInterceptor(jwtTokenAdminInterceptor)
                .addPathPatterns("/admin/**", "/notice/**")
                .excludePathPatterns("/admin/login")
                .excludePathPatterns("/admin/getCode")
                .excludePathPatterns("/admin/login/code")
                .excludePathPatterns("/notice/get")
                .excludePathPatterns("/notice/getList");
    }


    protected void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/doc.html").addResourceLocations("classpath:/META-INF/resources/");
        registry.addResourceHandler("/webjars/**").addResourceLocations("classpath:/META-INF/resources/webjars/");
    }

    protected void extendMessageConverters(List<HttpMessageConverter<?>> converters) {

        MappingJackson2HttpMessageConverter converter = new MappingJackson2HttpMessageConverter();
        converter.setObjectMapper(new JacksonObjectMapper());
        converters.add(0,converter);
    }
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**") // 允许跨域请求的所有路径
                .allowedOriginPatterns("*") // Spring6+凭据场景下 allowedOrigins("*") 非法,须用 pattern 形式
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS") // 允许的方法
                .allowedHeaders("*") // 允许的请求头
                ;
        }

}