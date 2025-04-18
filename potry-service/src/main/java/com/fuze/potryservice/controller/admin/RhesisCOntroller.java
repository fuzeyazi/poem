package com.fuze.potryservice.controller.admin;

import com.fuze.dto.RhesisDto;
import com.fuze.potryservice.service.AdminService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import groovy.util.logging.Slf4j;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController("名句管理端")
@Slf4j
@Api(tags = "名句管理相关接口")
public class RhesisCOntroller {
    @Autowired
    private AdminService adminService;
   @ApiOperation("分页展示所有名句")
   @GetMapping("/GetAll")
   public Result<PageResult> GetAll(
           @RequestParam(defaultValue = "1") Integer pageNum,
           @RequestParam(defaultValue = "10") Integer pageSize
   ){
       return Result.success(adminService.GetAllRhesis(pageNum,pageSize));
   }
   @ApiOperation("批量删除名句")
    @PostMapping("/delete")
    public Result delete(@RequestParam List<Integer> ids){
       adminService.deleteRhesisById(ids);
       return Result.success("删除成功");
   }
   @ApiOperation("添加名句")
    @PostMapping("/add")
    public Result add(@RequestBody RhesisDto rhesisDto){
       adminService.addRhesis(rhesisDto);
       return Result.success("添加成功");
    }
    @ApiOperation("修改名句")
    @PostMapping("/update")
    public Result update(@RequestBody RhesisDto rhesisDto){
        adminService.updateRhesis(rhesisDto);
        return Result.success("修改成功");
    }
    @ApiOperation("根据古诗名字模糊查询名句")
    @GetMapping("/getRhesisByPoemName")
    public Result<List<RhesisDto>> getRhesisByPoemName(@RequestParam String name){
        return Result.success(adminService.GetRhesisByPoemName(name));
    }
    @ApiOperation("获取名句数量")
    @GetMapping("/getCount")
    public Result<Long> getCount(){
        return Result.success(adminService.getRhesisCount());
    }
}
