package com.fuze.enumeration;

public enum EmailErrenum {
    EMAIL_IS_EXIST(201, "邮箱已经注册过了"),
    EMAIL_IS_BLANK(202, "邮箱不能为空"),
    EMAIL_OR_PWD_BLANK(203, "邮箱或密码不能为空"),
    INVALID_ADDRESSES(204, "无效的地址！"),
    VERIFY_IS_ERROR(205, "验证码错误"),
    REGISTER_FAIL(206, "注册失败"),
    EMAIL_OR_PWD_ERROR(206, "邮箱号或密码错误，登录失败");

    private Integer code;
    private String message;

    public String getMessage() {
        return message;
    }

    public Integer getCode() {
        return code;
    }

    //含参数构造;
    EmailErrenum(Integer code, String message) {
        this.message = message;
        this.code = code;
    }
}
