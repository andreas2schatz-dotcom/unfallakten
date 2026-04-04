import React from "react";

const Ic = {
  logo:     <svg viewBox="0 0 24 24" fill="currentColor" style={{width:22,height:22}}><text x="12" y="18" textAnchor="middle" fontFamily="Georgia,serif" fontSize="20" fontWeight="bold">§</text></svg>,
  dash:     <svg viewBox="0 0 24 24" fill="currentColor" style={{width:16,height:16}}><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>,
  akte:     <svg viewBox="0 0 24 24" fill="currentColor" style={{width:14,height:14}}><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>,
  x:        <svg viewBox="0 0 24 24" fill="currentColor" style={{width:13,height:13}}><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>,
  search:   <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>,
  user:     <svg viewBox="0 0 24 24" fill="currentColor" style={{width:16,height:16}}><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>,
  logout:   <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>,
  plus:     <svg viewBox="0 0 24 24" fill="currentColor" style={{width:14,height:14}}><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>,
  edit:     <svg viewBox="0 0 24 24" fill="currentColor" style={{width:13,height:13}}><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>,
  trash:    <svg viewBox="0 0 24 24" fill="currentColor" style={{width:13,height:13}}><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>,
  upload:   <svg viewBox="0 0 24 24" fill="currentColor" style={{width:28,height:28}}><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>,
  download: <svg viewBox="0 0 24 24" fill="currentColor" style={{width:13,height:13}}><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>,
  pdf:      <svg viewBox="0 0 24 24" fill="currentColor" style={{width:18,height:18}}><path d="M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-8.5 7.5c0 .83-.67 1.5-1.5 1.5H9v2H7.5V7H10c.83 0 1.5.67 1.5 1.5v1zm5 2c0 .83-.67 1.5-1.5 1.5h-2.5V7H15c.83 0 1.5.67 1.5 1.5v3zm4-3H19v1h1.5V11H19v2h-1.5V7h3v1.5zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6z"/></svg>,
  word:     <svg viewBox="0 0 24 24" fill="currentColor" style={{width:16,height:16}}><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zM6 20V4h7v5h5v11H6z"/></svg>,
  check:    <svg viewBox="0 0 24 24" fill="currentColor" style={{width:14,height:14}}><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>,
  chevR:    <svg viewBox="0 0 24 24" fill="currentColor" style={{width:13,height:13}}><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>,
  email:    <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>,
  refresh:  <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>,
  attach:   <svg viewBox="0 0 24 24" fill="currentColor" style={{width:13,height:13}}><path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/></svg>,
  settings: <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>,
  clock:    <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z"/></svg>,
  scale:    <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M17 3H7c-.55 0-1 .45-1 1v1H5c-.55 0-1 .45-1 1v1c0 .55.45 1 1 1h.09l1.38 8.28C6.2 17.47 6.93 18 7.77 18h8.46c.84 0 1.57-.53 1.3-1.72L18.91 8H19c.55 0 1-.45 1-1V6c0-.55-.45-1-1-1h-1V4c0-.55-.45-1-1-1zm1 4H6V6h12v1zm-2.23 9H8.23l-1.2-7.2h10.94l-1.2 7.2zM12 21c-1.1 0-2-.9-2-2h4c0 1.1-.9 2-2 2z"/></svg>,
  folder:   <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>,
  mail:     <svg viewBox="0 0 24 24" fill="currentColor" style={{width:15,height:15}}><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>,
};


export default Ic;
