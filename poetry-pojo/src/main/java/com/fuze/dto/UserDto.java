package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.context.annotation.Lazy;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor

public class UserDto {

    private String password;
    private String username;
    private String email;
    private String name;
    private String phone;
    private String sex;
    private String degree;



}
