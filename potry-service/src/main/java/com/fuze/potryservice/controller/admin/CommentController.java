package com.fuze.potryservice.controller.admin;

import com.fuze.dto.CommentDto;
import com.fuze.dto.CommentFindDto;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.AdminService;
import com.fuze.potryservice.service.CommentService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.CommentVo;
import com.github.pagehelper.PageInfo;
import groovy.util.logging.Slf4j;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import jakarta.websocket.server.PathParam;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController("adminCommentController")
@RequestMapping("/admin/blog")
@Api(tags = "帖子管理相关接口")
@Slf4j
public class CommentController {
 @Autowired
    private AdminService adminService;
 @ApiOperation("分页获取所有帖子")
    @GetMapping("/getAllBlog")
 public Result<PageResult> GetAllBlog(
         @RequestParam(defaultValue = "1") Integer pageNum,
         @RequestParam(defaultValue = "10") Integer pageSize
 ) {
     PageResult pageInfo = adminService.GetBlog(pageNum, pageSize);
     return Result.success(pageInfo);
 }
@ApiOperation("批量删除帖子")
    @PostMapping("/deleteBlog")
    public Result deleteBlog(@RequestParam List<Integer> ids) {
        adminService.deleteBlogById(ids);
        return Result.success();
    }

}