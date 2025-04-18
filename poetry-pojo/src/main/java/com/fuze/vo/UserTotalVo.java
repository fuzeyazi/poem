package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class UserTotalVo {
    private Integer id;
    private String username;
    //private String password;
    //角色扮演api的id
    // private String openid;
    //private String name;
    //先不传
    //private String touxiang;
    private String createtime;
    private String phone;
    //邮件也是
    private String email;
    private String sex;
    //也先不传
    private int age;
    private Integer status;
    //学历
    //private String degree;
    // private String nameTager;
}
