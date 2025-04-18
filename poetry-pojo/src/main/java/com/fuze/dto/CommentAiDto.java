package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.security.Timestamp;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class CommentAiDto {

        private Integer id;
        private String content;
        private String touxiang;
        private Integer thumbsUp;
        private Integer thumbsDown;
        private Integer replyCount;

}
