//package com.fuze.potryservice.config;
//
//import org.springframework.context.annotation.Bean;
//import org.springframework.context.annotation.Configuration;
//import org.springframework.web.cors.CorsConfiguration;
//import org.springframework.web.cors.CorsConfigurationSource;
//import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
//import org.springframework.web.servlet.config.annotation.CorsRegistry;
//import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
//
//
//import java.util.Arrays;
//
//@Configuration
//public class CorsConfig implements WebMvcConfigurer {
//    @Override
//    public void addCorsMappings(CorsRegistry registry) {
//        registry.addMapping("/**")
//                .allowedOrigins("http://example.com", "https://another-example.com")
//                .allowCredentials(true)
//                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
//                .allowedHeaders("*");
//    }
//
//}
