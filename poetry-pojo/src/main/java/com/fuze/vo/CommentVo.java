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
public class CommentVo {
    //帖子的id
    private Integer id;
    //用户的id
    private Integer userid;
    //
    private String username;
    //
    private String touxiang;
    //父评论id
    private Integer parentid;
    //内容
    private String content;
    //发布时间
    private String publishtime;
    //回复数
    private Integer replycount;
    //点赞数
    private Integer thumbsup;
    //点踩数
    private Integer thumbsdown;
    //状态
    private Integer status;
    //子评论
    private List<CommentVo> children;
    //判断是否被访问
    private boolean visited=false;


}
