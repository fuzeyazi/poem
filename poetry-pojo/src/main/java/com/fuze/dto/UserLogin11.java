package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class UserLogin11 {

    private String username;
    private String password;
    private String name;
    private String touxiang;
    private String phone;
    private String email;
    private String sex;
    private String degree;
    private int age;
}
