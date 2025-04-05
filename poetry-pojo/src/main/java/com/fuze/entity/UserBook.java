package com.fuze.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class UserBook {
    private Integer bookid;
    private Integer userid;
    private String bookname;
    private String description;
    private Integer sum;
    private Integer end;
}
