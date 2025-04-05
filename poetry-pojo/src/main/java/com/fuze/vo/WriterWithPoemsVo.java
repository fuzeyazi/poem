package com.fuze.vo;

import lombok.Data;
import java.util.List;

@Data

public class WriterWithPoemsVo {
    private Long id;
    private String name;
    private String headImageUrl;
    private String simpleIntro;
    private List<PoemVo> poems;
    }


