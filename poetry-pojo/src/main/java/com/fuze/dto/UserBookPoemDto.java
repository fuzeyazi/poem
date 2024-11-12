package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Builder
@Data
@AllArgsConstructor
@NoArgsConstructor
public class UserBookPoemDto {
    private Integer bookid;
    private Integer poemid;
     private Integer reviewCount; // 复习次数
 private LocalDate lastReviewDate; // 第一次加入的时间
 private LocalDate nextReviewDate; // 下一次复习日期
}
