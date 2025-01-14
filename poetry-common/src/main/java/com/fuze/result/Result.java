package com.fuze.result;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import java.io.Serializable;

/**
 * 后端统一返回结果
 *
 * @param <T>
 */
@Data
@ApiModel(description = "统一返回的数据模型")
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Result<T> implements Serializable {

    @ApiModelProperty("成功失败的代号")
    private Integer code; //编码：1成功，0和其它数字为失败
    @ApiModelProperty("简短描述")
    private String msg; //错误信息
    @ApiModelProperty("后端返回的数据")
    private T data; //数据

    public static <T> Result<T> success() {
        Result<T> result = new Result<T>();
        result.code = 1;
        return result;
    }

    public static <T> Result<T> success(T object) {
        Result<T> result = new Result<T>();
        result.data = object;
        result.code = 1;
        return result;
    }

    public static <T> Result<T> error(String msg) {
        Result result = new Result();
        result.msg = msg;
        result.code = 0;
        return result;
    }

}
