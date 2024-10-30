package com.fuze.result;

import io.swagger.annotations.ApiModel;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.List;

/**
 * 封装分页查询结果
 */
@Data
@AllArgsConstructor
@NoArgsConstructor
@ApiModel(description = "封装的分页查询结果")
public class PageResult implements Serializable {
    private long total; //总记录数
    private List records; //当前页数据集合

}
