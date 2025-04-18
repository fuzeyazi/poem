package com.fuze.dto;

import io.swagger.annotations.Api;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class WriterDto {
    private int id;
    private String name;
    private String headImageUrl;
    private String simpleIntro;
    private String detailIntro;
}
