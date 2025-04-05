package com.fuze.entity;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@Builder
@AllArgsConstructor

public class UserCollectionPoem implements Serializable {
    private static final long serialVersionUID = 1L;

    private Integer id;
    private Integer userid;
    private Integer poemid;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime collected_at;
}
