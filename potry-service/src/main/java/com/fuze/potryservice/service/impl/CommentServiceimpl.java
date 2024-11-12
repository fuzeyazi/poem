package com.fuze.potryservice.service.impl;

import com.fuze.entity.Comment;
import com.fuze.potryservice.mapper.CommentMapper;
import com.fuze.potryservice.service.CommentService;
import com.fuze.vo.CommentVo;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
public class CommentServiceimpl implements CommentService {
    @Autowired
    private CommentMapper commentMapper;

    @Override
    public void addcomment(Comment comment) {
        if (comment.getParentid() != null) {
            commentMapper.addcommentparentid(comment);
            //有个子评论，然后要更新父评论的回复数
            commentMapper.addreplycount(comment.getParentid());

        } else {
            commentMapper.addcomment(comment);
        }

    }

    @Override
    public void addthumb(Integer id) {
        if (id != 0) {
            commentMapper.addthumb(id);
        } else {
            commentMapper.deletethumb(id);
        }
    }




    @Override
    public PageInfo<CommentVo> getCommentList(Integer pageNum, Integer pageSize) {
        PageHelper.startPage(pageNum, pageSize);
        List<CommentVo> lis1 = commentMapper.getCommentList();
        return new PageInfo<>(lis1);
    }
    //下面全是论坛
    @Override
    public CommentVo getCommentDetails(Integer id) {
        Comment post=commentMapper.findbyid(id);
        System.out.println(post);

        if (post == null) {
            return null;
        }
        CommentVo postVo = convertToCommentVo(post);
        Set<Integer> visitedIds = new HashSet<>();
        postVo.setChildren(getChildren(postVo,visitedIds));

        return postVo;
    }

    private CommentVo convertToCommentVo(Comment comment) {
        CommentVo vo = new CommentVo();
        vo.setId(comment.getId());
        vo.setUserid(comment.getUserid());
        vo.setParentid(comment.getParentid());
        vo.setContent(comment.getContent());
        vo.setPublishtime(comment.getPublishtime());
        vo.setReplycount(comment.getReplycount());
        vo.setThumbsup(comment.getThumbsup());
        vo.setThumbsdown(comment.getThumbsdown());
        vo.setStatus(comment.getStatus());
        return vo;

    }
    private List<CommentVo> getChildren(CommentVo parentVo,  Set<Integer> visitedIds) {
        List<CommentVo> children = new ArrayList<>();
        List<Comment> comments = commentMapper.findByParentId(parentVo.getId());
        if (comments.isEmpty()) {
            return children;
        }
        for (Comment comment : comments) {
            CommentVo childVo = convertToCommentVo(comment);
            // 检查是否已经处理过该评论
            if (!visitedIds.contains(childVo.getId())) {
                visitedIds.add(childVo.getId()); // 添加到已处理 ID 集合
                // 递归调用，增加当前深度
                childVo.setChildren(getChildren(childVo,visitedIds));
                children.add(childVo);
            }
           }


        return children;
    }
}

