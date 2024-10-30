package com.fuze.potryservice.controller.user;

import com.fuze.dto.CommentDto;
import com.fuze.entity.Comment;
import com.fuze.potryservice.mapper.CommentMapper;
import com.fuze.potryservice.service.CommentService;
import com.fuze.potryservice.service.UserService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.CommentVo;
import com.github.pagehelper.PageInfo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/user/Comment")
@Api(tags ="用户关于论坛的相关接口，我们叫文坛")
@Slf4j
public class CommentController {
    @Autowired
    private CommentService commentService;
    @Autowired
    private UserService userService;
    @Autowired
    private CommentMapper commentMapper;


    @ApiOperation("发布帖子")
    @RequestMapping("/addcomment")
    public Result<String> addcomment(@RequestBody CommentDto commentdto){
        //获取用户头像
        String touxiang=userService.gettouxiangbyid(commentdto.getUserid());
        //获取用户昵称
        String username=userService.getusernamebyid(commentdto.getUserid());
        try {Comment comment = new Comment();
            BeanUtils.copyProperties(commentdto, comment);
            comment.setUsername(username);
            comment.setTouxiang(touxiang);
            log.info("发布帖子：{}",comment);
            commentService.addcomment(comment);
            return Result.success("发布成功");

        }catch (Exception e){
            return Result.error("发布失败");
        }

    }
    @ApiOperation("点赞或则点踩帖子，0为赞，1为踩")
    @PostMapping("/thumb")
    //提供评论或者帖子的id就行,还有点赞还是踩
    public Result<String> addthumb(@RequestParam Integer id,@RequestParam Integer type){
        if(type==0){
            commentService.addthumb(id);
            return Result.success("点赞成功");
        }else {
            commentMapper.deletethumb(id);
            return Result.success("点踩成功");
        }

    }

    @ApiOperation("回复帖子,简称评论")
    @PostMapping("/reply")
    //获取父评论的id，和回复的内容
    public Result<String> reply(@RequestParam Integer parentid,@RequestParam String content,@RequestParam Integer userid){
        Comment comment=new Comment();
        comment.setContent(content);
        comment.setParentid(parentid);
        comment.setStatus(1);
        //获取用户头像
        String touxiang=userService.gettouxiangbyid(userid);
        //获取用户昵称
        String username=userService.getusernamebyid(userid);
        comment.setTouxiang(touxiang);
        comment.setUsername(username);
        //添加评论,并且也会增加父评论的回复数,而且父评论的的childernid也要添加评论的id
        commentService.addcomment(comment);
        return Result.success("回复成功");
    }
@ApiOperation("展示部分帖子信息，做个分页处理")
    @GetMapping("/getcomment")
    public Result<PageResult> getCommentList(@RequestParam(defaultValue = "1") Integer pageNum, @RequestParam(defaultValue = "20") Integer pageSize){
    PageInfo<CommentVo> pageInfo=commentService.getCommentList(pageNum,pageSize);
    return Result.success(new PageResult(pageInfo.getTotal(),pageInfo.getList()));
}

@ApiOperation("展示帖子的详细信息")
  @GetMapping("/getcommentxaingxi/{id}")
    public Result<CommentVo>  getcommentxaingxi(@PathVariable Integer id){
    CommentVo commentVo = commentService.getCommentDetails((Integer) id);
    if (commentVo == null) {
        return Result.error("帖子不存在");
    }
        return Result.success(commentVo);
}


}
