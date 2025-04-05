package com.fuze.response;

import lombok.Data;
import org.springframework.context.annotation.Lazy;

/**
 * Created with IntelliJ IDEA
 *
 * @author zhwang40
 * @date：2024/3/21
 * @time：14:32
 * @descripion:
 */
@Data
@Lazy
public class ResponseMsg<T> {
    private boolean success;

    private Integer code;

    private String message;

    private T data;

    private String sid;
}
