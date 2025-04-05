package com.fuze.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class FeedBack implements Serializable {
    private static final long serialVersionUID = 1L;

    private Integer id;
    private Integer userid;
    private String messsage;
    private LocalDateTime createtime;
}
