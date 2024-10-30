package com.fuze.potryservice.service;

import com.fuze.entity.Comment;
import com.fuze.vo.CommentVo;
import com.github.pagehelper.PageInfo;

public interface CommentService {
    void addcomment(Comment comment);

    void addthumb(Integer id);

    PageInfo<CommentVo> getCommentList(Integer pageNum, Integer pageSize);

    CommentVo getCommentDetails(Integer id);
}
