package com.fuze.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Date;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class Admin {
    private Long id;
    private String username;
    private String password;
    private String email;
    private String phone;
    private Integer status;
    private Date createdAt;
    private Date updatedAt;
}
