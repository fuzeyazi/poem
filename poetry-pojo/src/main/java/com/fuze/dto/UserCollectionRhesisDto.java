package com.fuze.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

@Builder
@Data
@AllArgsConstructor
@NoArgsConstructor
public class UserCollectionRhesisDto implements Serializable {
    private static final long serialVersionUID = 1L;
    private Integer userid;
    private Integer rhesisid;
}
