package com.fuze.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class Poem {
   private String id;
    private  String title;
    private  String dynasty;
    private  String writer;
    private  String type;
    private String content;
    private String remarks;
    private String translation;
    private String shangxi;
    private String audiourl;
}
