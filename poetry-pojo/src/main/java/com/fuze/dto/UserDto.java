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

    private Integer id;

    private String password;

    private String username;

    private String name;

    private String phone;

    private String sex;




}
