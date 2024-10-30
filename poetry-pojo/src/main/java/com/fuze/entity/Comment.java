package com.fuze.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class Comment {
    private Integer id;
    private Integer userid;
    private String content;//发布内容
    private String publishtime;//发布时间
    private String username;//用户名
    private Integer thumbsup;//点赞数量
    private Integer thumbsdown;//点踩数量
    private Integer replycount;//回复的数量
    private String touxiang;//发布者的头像
    private Integer parentid;//父评论id，没有就是null
//如果是null说明就是帖子
    private Integer status;


}
