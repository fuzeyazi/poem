package com.fuze.potryservice.controller.admin;

import com.fuze.dto.PotryDTO;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.AdminService;
import com.fuze.potryservice.service.PotryService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController("管理端")
@RequestMapping("/admin/potry")
@Api(tags = "诗词管理的相关接口")
@Slf4j
public class PotryController {
    @Autowired
    private  PotryService potryService;
    @Autowired
    private AdminService adminService;
    @ApiOperation(value = "获取古诗的数量")
    @GetMapping("/GetCount")
    public Result<Integer> GetCount() {
        //直接调用
        log.info("获取现存古诗数量执行:");
        Integer count = potryService.getcount();
        return Result.success(count);
    }
    @ApiOperation(value = "添加古诗")
    @AutoLog(value = "添加古诗")
    @PostMapping("/add")
public Result add(@RequestBody PotryDTO potryDTO) {
        log.info("添加古诗执行:");
        adminService.add(potryDTO);
        return Result.success("添加成功");
    }
    @ApiOperation(value = "批量删除古诗")
    @AutoLog(value = "删除古诗")
    @PostMapping("/delete")
    public Result delete(@RequestBody List<Long> ids) {
        log.info("批量删除古诗执行:");
        adminService.delete(ids);
        return Result.success("删除成功");
    }
@ApiOperation(value = "修改古诗")
@AutoLog(value = "修改古诗")
    @PostMapping("/update")
    public Result update(@RequestBody PotryDTO potryDTO) {
        log.info("修改古诗执行:");
        adminService.update(potryDTO);
        return Result.success("修改成功");
    }
    @ApiOperation("模糊查询古诗")
    @GetMapping("/getPoem")
    public Result<List<PotryDTO>> getPoem(@RequestBody PotryDTO potryDTO) {
        log.info("模糊查询古诗执行:");
        List<PotryDTO> poem = adminService.GetContent(potryDTO);
        if (poem.isEmpty())
        {
            return Result.error("未查询到古诗");
        }
        return Result.success(poem);
    }
    @ApiOperation("根据标题删除古诗")
    @PostMapping("/deletePoem")
    public Result deletePoem(String title) {
        log.info("根据标题删除古诗执行:");
        adminService.deleteByTitle(title);
        return Result.success("删除成功");
    }
    @ApiOperation("分页获取所有古诗")
    @GetMapping("/GetPoemPage")
    public Result<PageResult> GetLog(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize
    ) {
        PageResult pageInfo = adminService.GetPoem(pageNum, pageSize);
        return Result.success(pageInfo);
    }

}
