package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class FabaCommnetVo {
    private Integer blogid;
    private String name;
    private String touxiang;
    private String context;
    private LocalDateTime createTiem;
    private Integer liked;
    private Integer conment;
    private Integer parentId;
    private String tagerrName;
    private  Integer id;
    List<FabaCommnetVo> children;
}
