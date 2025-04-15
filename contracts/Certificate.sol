// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Certificate {
    struct CertificateData {
        uint256 id;
        string certificateName;
        string issuedBy;
        string issueDate;
        string expiryDate;
        address owner;
    }
    
    mapping(uint256 => CertificateData) public certificates;
    uint256 public nextCertificateId = 1;
    
    function issueCertificate(
        string memory certificateName,
        string memory issuedBy,
        string memory issueDate,
        string memory expiryDate
    ) public returns (uint256) {
        uint256 certId = nextCertificateId;
        
        certificates[certId] = CertificateData({
            id: certId,
            certificateName: certificateName,
            issuedBy: issuedBy,
            issueDate: issueDate,
            expiryDate: expiryDate,
            owner: msg.sender
        });
        
        nextCertificateId++;
        return certId;
    }
    
    function getCertificate(uint256 certificateId) public view returns (
        uint256, string memory, string memory, string memory, string memory, address
    ) {
        require(certificateId > 0 && certificateId < nextCertificateId, "Certificate does not exist");
        CertificateData storage cert = certificates[certificateId];
        
        return (
            cert.id,
            cert.certificateName,
            cert.issuedBy,
            cert.issueDate,
            cert.expiryDate,
            cert.owner
        );
    }
}
