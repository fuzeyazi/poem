package com.fuze.potryservice.controller.admin;

import com.fuze.dto.CommentAiDto;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.AdminService;
import com.fuze.potryservice.service.CommandService;
import com.fuze.potryservice.service.CommentService;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/command")
@Api(tags = "AI指令处理")
public class AICommandController {

    @Autowired
    private CommandService commandService;
    @Autowired
    private CommentService commentService;
@ApiOperation("处理AI指令")
@AutoLog("使用AI指令")
@PostMapping("/handle")
public Result handleCommand(@RequestParam  String command) {
    return Result.success(commandService.process(command));
}
    @ApiOperation("对论坛数据分析")
    @PostMapping("/forum")
    public Result forumDataAnalysis(@RequestBody CommentAiDto commentAiDto){
        List<String> list = commentService.getListBy(commentAiDto.getId());
        return Result.success(commandService.process1(commentAiDto,list));
    }
}