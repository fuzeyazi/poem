package com.fuze.entity;


import java.time.LocalDateTime;
import java.io.Serializable;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.*;
import lombok.experimental.Accessors;

/**
 * <p>
 * 
 * </p>
 *
 * @author author
 * @since 2024-11-13
 */
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
@EqualsAndHashCode(callSuper = false)
@Accessors(chain = true)
@ApiModel(value="PoemBlog对象", description="")
public class PoemBlog implements Serializable {
    private static final long serialVersionUID = 1L;
    private Integer id;
    private Integer poemId;
    private Integer userId;
    private String title;
    private String images;
    private String content;
    private Integer liked;
    @ApiModelProperty(value = "评论数量")
    private Integer conmments;
    private String poemword;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private String type;
    private boolean islike;

}
