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
public class reply implements Serializable {
    private static final long serialVersionUID = 1L;
    private Integer id;
    private String  feedbackmsg;
    private  Integer userid;
    private LocalDateTime localDateTime;
    private String message;
    private Integer feedbackid;




}
