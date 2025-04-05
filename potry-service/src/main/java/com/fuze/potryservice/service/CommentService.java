package com.fuze.potryservice.service;

import com.fuze.dto.CommentFindDto;
import com.fuze.entity.Comment;
import com.fuze.vo.CommentVo;
import com.github.pagehelper.PageInfo;

import java.util.List;

public interface CommentService {
    void addcomment(Comment comment);

    void addthumb(Integer id);

    PageInfo<CommentVo> getCommentList(Integer pageNum, Integer pageSize);

    CommentVo getCommentDetails(Integer id);

    List<CommentVo> getCommentListBy(CommentFindDto commentFinDto);

    void deleteComment(List<Long> id);
}
