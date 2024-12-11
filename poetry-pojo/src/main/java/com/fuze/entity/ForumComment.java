package com.fuze.entity;

import java.time.LocalDateTime;
import java.io.Serializable;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.*;
import lombok.experimental.Accessors;

/**
 * <p>
 * 评论表
 * </p>
 *
 * @author author
 * @since 2024-11-15
 */
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class ForumComment implements Serializable {
    private static final long serialVersionUID = 1L;
    private Integer id;
    private Integer blogId;
    private Integer userId;
    private String context;
    private LocalDateTime createTiem;
    private Integer parentId;
    private Integer liked;
    private Integer conment;
    private String tagername;
}
