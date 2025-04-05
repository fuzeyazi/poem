package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class PotryDTO {
    private int id;
    private String title;
    private String dynasty;
    private String writer;
    private String content;
    private String type;
}
