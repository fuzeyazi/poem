package com.fuze.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class QuestionsGame {
    private Integer id;
    private String userid;
    private String grand;
    private String coutTime;
    private String usename;

}
