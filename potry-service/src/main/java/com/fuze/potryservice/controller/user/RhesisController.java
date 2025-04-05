package com.fuze.potryservice.controller.user;

import com.fuze.entity.Poem;
import com.fuze.entity.Rhesis;
import com.fuze.potryservice.service.RhesisService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import com.fuze.vo.PoemDataVo;
import com.fuze.vo.RhesisDataVo;
import com.github.pagehelper.PageInfo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/user/rhesis")
@Api(tags ="用户对名句的相关操作")
@Slf4j
public class RhesisController {
    @Autowired
    private RhesisService rhesisService;
    @ApiOperation(value = "获取名句的数量")
    @GetMapping("/GetCount")
    public Result<Integer> GetCount(){
        log.info("获取现存名句数量执行:");
        Integer count=rhesisService.getcount();
        return Result.success(count);
    }
    @ApiOperation(value = "获取所有名句的内容")
    @GetMapping("/GetAllRhesisName")
    public Result<List<String>>GetAllRhesisName(){
        log.info("获取所有名句执行:");
        List<String> list=rhesisService.GetAllRhesisName();
        return Result.success(list);
    }
    @ApiOperation(value = "通过单个id获取名句")
    @GetMapping("/GetRhesisContentById/{id}")
    public Result<Rhesis>GetContentById(@PathVariable Integer id){
        log.info("通过id获取名句内容执行:");
        Rhesis rhesis=rhesisService.GetContentById(id);
        return Result.success(rhesis);
    }
    @ApiOperation(value = "随机获得获得一句名句，今日推荐")
    @GetMapping("/GetVeryGoodRhesis")
    public Result<RhesisDataVo>GetVeryGoodPoem(){
        return Result.success(rhesisService.GetVeryGoodRhesis());
    }
    @ApiOperation(value = "搜索关键词获取名句")
    @GetMapping("/GetRhesisByKey/{keyword}")
    public Result<List<RhesisDataVo>>GetRhesisByKey(@PathVariable String keyword){
        List<RhesisDataVo> list=rhesisService.GetRhesisByKey(keyword);
        return Result.success(list);
    }
    @ApiOperation(value = "随机返回十条名句数据")
    @GetMapping("/GetRhesisDateRondom")
    public Result<List<RhesisDataVo>>GetRhesisDateRondom(){
        List<RhesisDataVo> list=rhesisService.GetRhesisDateRondom();
        return Result.success(list);
    }
    @ApiOperation(value = "分页查询名句（一次获得20条名句数据）")
    @GetMapping("/GetRhesisPage")
    public  Result<PageResult> GetRhesisPage(@RequestParam(defaultValue = "1") Integer pageNum, @RequestParam(defaultValue = "20") Integer pageSize)
    {         PageInfo<RhesisDataVo> pageInfo=rhesisService.GetRhesisPage(pageNum, pageSize);
        return Result.success(new PageResult(pageInfo.getTotal(),pageInfo.getList()));
    }

}
