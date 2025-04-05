package com.fuze.vo;

import io.swagger.annotations.ApiModelProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class UserVo {
    @ApiModelProperty("用户的id")
    private Integer id;
    @ApiModelProperty("用户账号")
    private String username;
    @ApiModelProperty("用户网名")
    private String name;
    @ApiModelProperty("用户的openid")
    private String openid;
    @ApiModelProperty("用户的avatarurl")
    private String touxiang;
    @ApiModelProperty("token值")
    private String token;
    @ApiModelProperty("用户的学历")
    private String degree;
}
