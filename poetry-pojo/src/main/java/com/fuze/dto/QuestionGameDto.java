package com.fuze.dto;

import lombok.Builder;
import lombok.Data;

@Builder
@Data
public class QuestionGameDto {
    private String userId;
    private String grand;
}
